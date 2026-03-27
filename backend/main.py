from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import List, Dict, Optional
from pathlib import Path
import io
import gzip
import pandas as pd
from pydantic import BaseModel
from sklearn.decomposition import PCA

from nlp.embeddings import generate_embeddings, EmbeddingConfig
from ml.dedup_engine import DedupEngine, DedupConfig
from ml.root_cause_graph import RootCauseAnalyzer
from ml.causal_inference import estimate_causal_score

from parser import parse_logs
from preprocessor import preprocess_records
from categorizer import categorize_messages
from deduplicator import deduplicate
from clusterer import cluster_embeddings
from scorer import compute_scores, optimize_weights, prioritize_failures
from services.pipeline import process_log_text
from auth_utils import verify_password, hash_password
from mongo_store import (
    init_mongo,
    create_run,
    add_failures,
    get_run,
    get_runs,
    get_failures_by_run,
    delete_run,
    get_history_counts,
    create_upload_job,
    get_upload_job,
    set_upload_job_status,
    update_failure_status,
    get_failure_by_id,
    get_user_by_username,
    create_user,
    admin_exists,
    get_weights,
    set_weights,
    revoke_token,
    is_token_revoked,
)

app = FastAPI(title="DebugIQ API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from loguru import logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator
import time
import uuid
import jwt
import os
import pika
from dotenv import load_dotenv

# Load env from backend/.env explicitly (works regardless of cwd)
load_dotenv(dotenv_path=(Path(__file__).resolve().parent / ".env"))

SECRET_KEY = os.environ.get("DEBUGIQ_JWT_SECRET", "debugiq_dev_only_secret_change_me")
ALGORITHM = "HS256"
ADMIN_USERNAME = os.environ.get("DEBUGIQ_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("DEBUGIQ_ADMIN_PASSWORD", "admin123")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

Instrumentator().instrument(app).expose(app)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_access_token(data: dict):
    to_encode = data.copy()
    to_encode.update({"exp": int(time.time()) + 3600, "jti": str(uuid.uuid4())})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

class SignupRequest(BaseModel):
    username: str
    password: str
    role: str  # admin | user

@app.get("/auth/admin-exists")
def auth_admin_exists():
    return {"admin_exists": admin_exists()}

@app.post("/signup")
@limiter.limit("10/minute")
def signup(request: Request, payload: SignupRequest):
    role = payload.role.strip().lower()
    if role not in {"admin", "user"}:
        raise HTTPException(status_code=400, detail="Invalid role")

    if get_user_by_username(payload.username):
        raise HTTPException(status_code=400, detail="Username already exists")
    if role == "admin" and admin_exists():
        raise HTTPException(status_code=400, detail="Admin already exists")

    user = create_user(payload.username, hash_password(payload.password), role)

    token = create_access_token({"sub": user["username"], "role": user["role"]})
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}

@app.post("/token")
@limiter.limit("10/minute")
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect credentials")

    token = create_access_token({"sub": user["username"], "role": user["role"]})
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}

@app.post("/logout")
@limiter.limit("20/minute")
def logout(request: Request, token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            revoke_token(jti, exp)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return {"status": "logged_out"}

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role", "user")
        jti = payload.get("jti")
        if jti and is_token_revoked(jti):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")
        user = get_user_by_username(username) if username else None
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return {"username": username, "role": role, "user_id": user["_id"]}
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

@app.get("/secure-data")
@limiter.limit("100/minute")
def secure_data(request: Request, user: str = Depends(get_current_user)):
    return {"message": f"Hello {user['username']}, this is a protected route.", "role": user["role"]}

ROOT_CAUSE_MAP = {
    "uvm_fatal": "UVM fatal: check testbench stop conditions, fatal assertions, and upstream UVM components",
    "uvm_error": "UVM error: trace sequence, scoreboard, and driver/monitor interactions",
    "uvm_warning": "UVM warning: inspect non-fatal protocol or coverage warnings",
    "uvm_phase_error": "UVM phase error: validate build/connect/run phase ordering and objections",
    "uvm_sequence_error": "UVM sequence error: inspect sequencer arbitration and sequence item flow",
    "uvm_scoreboard_mismatch": "Scoreboard mismatch: compare expected vs actual transactions and predictors",
    "sva_assertion_failure": "SVA assertion failure: inspect assertion antecedent and signal stability window",
    "assertion_failure": "Possible cause: violated design assumption; inspect surrounding signals",
    "timeout_error": "Possible cause: clock domain issue or stalled handshake",
    "protocol_violation": "Possible cause: incorrect sequencing; verify FSM transitions",
    "data_mismatch": "Possible cause: pipeline stage data corruption; check write-back logic",
    "memory_error": "Possible cause: address decode failure or ECC mismatch",
}

RECOMMEND_MAP = {
    "uvm_fatal": "Identify fatal source, check UVM fatal triggers, and confirm correct test termination behavior",
    "uvm_error": "Trace UVM components: sequencer, driver, monitor, and check scoreboard comparisons",
    "uvm_warning": "Review UVM warning text and investigate underlying protocol or coverage issues",
    "uvm_phase_error": "Check phase transitions and objections; ensure phase callbacks are registered",
    "uvm_sequence_error": "Review sequence constraints and arbitration; validate sequence item flow",
    "uvm_scoreboard_mismatch": "Inspect scoreboard compare logs; verify predictors and reference model",
    "sva_assertion_failure": "Validate assertion trigger signals and timing; check antecedent stability",
    "assertion_failure": "Inspect assertion conditions and triggering signals; validate channel ordering and ready/valid behavior",
    "timeout_error": "Check clock gating logic; verify handshake completion signals",
    "protocol_violation": "Review FSM state transitions; validate protocol sequencing",
    "data_mismatch": "Trace data path; check pipeline registers and write-back stages",
    "memory_error": "Verify address decoder; check ECC logic and memory interface",
}

class DeduplicateRequest(BaseModel):
    logs: List[str]
    similarity_threshold: Optional[float] = None

class FeedbackItem(BaseModel):
    severity: str
    module: str
    frequency: int
    is_critical: bool
    history: int | None = 0
    module_impact: float | None = 1.0

class PrioritizeRequest(BaseModel):
    feedback: List[FeedbackItem]


class FailureStatusUpdate(BaseModel):
    status: str


def _read_upload(upload: UploadFile) -> str:
    if not upload.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    raw = upload.file.read()
    if upload.filename.endswith(".gz"):
        try:
            raw = gzip.decompress(raw)
        except OSError as exc:
            raise HTTPException(status_code=400, detail="Invalid gzip file") from exc
    try:
        return raw.decode("utf-8", errors="ignore")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Unable to decode file") from exc


QUEUE_NAME = "debugiq_uploads"


def _publish_upload_job(job_id: int) -> None:
    """
    Enqueue a log-processing job to RabbitMQ.
    Worker consumes from `QUEUE_NAME`.
    """
    rabbit_url = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
    params = pika.URLParameters(rabbit_url)
    connection = pika.BlockingConnection(params)
    try:
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_NAME, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=QUEUE_NAME,
            body=str(job_id).encode("utf-8"),
            properties=pika.BasicProperties(delivery_mode=2),
        )
    finally:
        connection.close()


def _health_score(total: int, unique: int) -> float:
    if total == 0:
        return 100.0
    duplicates = max(total - unique, 0)
    score = (duplicates / total) * 100.0
    return round(score, 2)


def _to_dataframe(failures: List[Dict]) -> pd.DataFrame:
    return pd.DataFrame(failures)


@app.on_event("startup")
def on_startup() -> None:
    init_mongo()
    # Seed a single fixed admin if none exists.
    if not admin_exists():
        try:
            create_user(ADMIN_USERNAME, hash_password(ADMIN_PASSWORD), "admin")
            logger.info("Seeded initial admin user from environment.")
        except Exception as exc:
            logger.warning("Failed to seed admin user: %s", exc)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/root-cause/{run_id}/{failure_id}")
@limiter.limit("40/minute")
def api_root_cause(
    request: Request,
    run_id: int,
    failure_id: int,
    user: str = Depends(get_current_user),
):
    run = get_run(run_id, user_id=user["user_id"])
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    failures = get_failures_by_run(run_id)
        
    failures_list = [{
        "id": f["_id"],
        "timestamp": f.get("timestamp"),
        "module": f.get("module"),
        "category": f.get("category"),
        "severity": f.get("severity")
    } for f in failures]
    
    analyzer = RootCauseAnalyzer()
    analyzer.build_temporal_graph(failures_list)
    causes = analyzer.analyze_root_cause(failure_id)

    scored = []
    for c in causes:
        scored.append({**c, "causal_score": estimate_causal_score(c, failures_list)})
    
    return {"target_failure_id": failure_id, "potential_root_causes": scored}


@app.get("/explain/{run_id}/{failure_id}")
@limiter.limit("40/minute")
def api_explain(
    request: Request,
    run_id: int,
    failure_id: int,
    user: str = Depends(get_current_user),
):
    run = get_run(run_id, user_id=user["user_id"])
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    failures = get_failures_by_run(run_id)

    target_failure = next((f for f in failures if f["_id"] == failure_id), None)
    if not target_failure:
        raise HTTPException(status_code=404, detail="Failure not found")

    from ml.explainability import generate_llm_explanation, compute_shap_importance
    from scorer import get_current_weights, SEVERITY_WEIGHTS, MODULE_WEIGHTS
    import numpy as np

    failure_context = {
        "id": target_failure["_id"],
        "module": target_failure.get("module"),
        "severity": target_failure.get("severity"),
        "category": target_failure.get("category"),
        "message": target_failure.get("message"),
        "context": target_failure.get("context"),
    }

    try:
        explanation = generate_llm_explanation(failure_context)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"LLM provider error: {str(exc)}")
    
    features_list = []
    freq_map = {}
    for f in failures:
        key = f.get("unique_failure_id")
        freq_map[key] = freq_map.get(key, 0) + 1
    max_freq = max(freq_map.values()) if freq_map else 1

    feature_names = ["severity", "frequency", "module"]
    ordered_failures = [target_failure] + [f for f in failures if f["_id"] != failure_id]
    
    for f in ordered_failures:
        sev_w = SEVERITY_WEIGHTS.get(f.get("severity"), 0.1)
        freq_w = freq_map.get(f.get("unique_failure_id"), 0) / max_freq
        mod_w = MODULE_WEIGHTS.get(f.get("module"), 0.5)
        features_list.append([sev_w, freq_w, mod_w])
        
    features_array = np.array(features_list)
    weights = get_weights() or get_current_weights()
    shap_importance = compute_shap_importance(features_array, feature_names, weights)

    return {
        "failure_id": failure_id,
        "llm_explanation": explanation,
        "shap_importance": shap_importance
    }


@app.post("/deduplicate")
@limiter.limit("60/minute")
def api_deduplicate(
    request: Request,
    req: DeduplicateRequest,
    user: str = Depends(get_current_user),
):
    cfg = DedupConfig()
    if req.similarity_threshold is not None:
        cfg.similarity_threshold = req.similarity_threshold
    engine = DedupEngine(cfg)
    unique_ids, is_duplicate, _embeddings = engine.deduplicate(req.logs)
    return {
        "unique_ids": unique_ids,
        "is_duplicate": is_duplicate,
        "total_logs": len(req.logs),
        "unique_count": len(set(unique_ids)) if unique_ids else 0,
        "duplicate_count": int(sum(1 for flag in is_duplicate if flag)),
    }


@app.post("/prioritize")
@limiter.limit("60/minute")
def api_prioritize(
    request: Request,
    req: PrioritizeRequest,
    user: str = Depends(get_current_user),
):
    data = [item.dict() for item in req.feedback]
    new_weights = optimize_weights(data)
    set_weights(new_weights)
    ranked = prioritize_failures(data)
    return {"new_weights": new_weights, "ranked_failures": ranked}


@app.post("/upload")
@limiter.limit("5/minute")
def upload_log(
    request: Request,
    file: UploadFile = File(...),
    user: str = Depends(get_current_user),
):
    text = _read_upload(file)
    try:
        return process_log_text(text, file.filename or "upload.log", user_id=user["user_id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/upload-async")
@limiter.limit("5/minute")
def upload_log_async(
    request: Request,
    file: UploadFile = File(...),
    user: str = Depends(get_current_user),
):
    text = _read_upload(file)
    job = create_upload_job(file.filename or "upload.log", text, user_id=user["user_id"])
    _publish_upload_job(job["_id"])
    return {"job_id": job["_id"]}


@app.get("/job-status/{job_id}")
@limiter.limit("40/minute")
def api_job_status(
    request: Request,
    job_id: int,
    user: str = Depends(get_current_user),
):
    job = get_upload_job(job_id, user_id=user["user_id"])
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job["_id"], "status": job["status"], "run_id": job["run_id"], "error": job.get("error")}


@app.post("/debug-upload")
@limiter.limit("20/minute")
async def debug_upload(
    request: Request,
    file: UploadFile = File(...),
    user: str = Depends(get_current_user),
):
    content = await file.read()
    text = content.decode("utf-8", errors="ignore")
    lines = text.splitlines()
    return {
        "total_lines": len(lines),
        "first_10_lines": lines[:10],
        "file_size_bytes": len(content),
    }


@app.get("/dashboard/{run_id}")
@limiter.limit("40/minute")
def get_dashboard(
    request: Request,
    run_id: int,
    user: str = Depends(get_current_user),
):
    run = get_run(run_id, user_id=user["user_id"])
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    failures = get_failures_by_run(run_id)

    if not failures:
        raise HTTPException(status_code=404, detail="No failures found")

    df = pd.DataFrame([{
        "id": f["_id"],
        "timestamp": f.get("timestamp"),
        "sim_time": f.get("sim_time"),
        "severity": f.get("severity"),
        "severity_raw": f.get("severity_raw"),
        "failure_type": f.get("failure_type"),
        "module": f.get("module"),
        "line_no": f.get("line_no"),
        "message": f.get("message"),
        "context": f.get("context"),
        "test_name": f.get("test_name"),
        "seed": f.get("seed"),
        "dut_path": f.get("dut_path"),
        "uvm_phase": f.get("uvm_phase"),
        "source_file": f.get("source_file"),
        "source_line": f.get("source_line"),
        "category": f.get("category"),
        "cluster_id": f.get("cluster_id"),
        "priority_score": f.get("priority_score"),
        "is_duplicate": f.get("is_duplicate"),
        "unique_failure_id": f.get("unique_failure_id"),
        "status": f.get("status"),
        "first_seen_run_id": f.get("first_seen_run_id"),
        "last_seen_run_id": f.get("last_seen_run_id"),
        "first_seen_at": f.get("first_seen_at"),
        "last_seen_at": f.get("last_seen_at"),
        "closed_at": f.get("closed_at"),
    } for f in failures])

    # Use explicit counting to ensure label fields are always present.
    category_counts = df["category"].value_counts().to_dict()
    category_distribution = [
        {"category": key, "count": int(val)} for key, val in category_counts.items()
    ]

    module_counts = df["module"].value_counts().to_dict()
    module_hotspots = [
        {"module": key, "count": int(val)} for key, val in module_counts.items()
    ]

    freq_map = df["unique_failure_id"].value_counts().to_dict()

    priority_ranking = (
        df.sort_values("priority_score", ascending=False)
        .assign(rank=lambda d: range(1, len(d) + 1))
        [["rank", "severity", "module", "category", "priority_score", "unique_failure_id"]]
        .rename(columns={"priority_score": "score"})
        .assign(frequency=lambda d: d["unique_failure_id"].map(freq_map))
        .to_dict(orient="records")
    )

    # Build an adaptive timeline histogram so the chart is informative for both
    # short and long logs (avoid mostly-flat count=1 lines).
    ts_series = pd.to_datetime(df["timestamp"], errors="coerce")
    if ts_series.notna().any():
        sec = (ts_series.astype("int64") // 1_000_000_000).astype("int64")
        sec_min = int(sec.min())
        sec_max = int(sec.max())
        span = max(sec_max - sec_min + 1, 1)
        target_bins = 24
        bin_width_sec = max(1, int((span + target_bins - 1) // target_bins))

        bucket = ((sec - sec_min) // bin_width_sec) * bin_width_sec + sec_min
        timeline_df = pd.DataFrame({"bucket": bucket})
        failure_timeline = (
            timeline_df.groupby("bucket").size().reset_index(name="count")
            .sort_values("bucket")
        )
        failure_timeline["time"] = pd.to_datetime(
            failure_timeline["bucket"], unit="s"
        ).dt.strftime("%H:%M:%S")
        failure_timeline = failure_timeline[["time", "count"]].to_dict(orient="records")
    else:
        # Fallback: monotonic bucket by parsed row index if timestamps are unusable.
        n = len(df)
        target_bins = 24
        bucket_size = max(1, (n + target_bins - 1) // target_bins)
        idx_df = pd.DataFrame({"bucket": [i // bucket_size for i in range(n)]})
        failure_timeline = (
            idx_df.groupby("bucket").size().reset_index(name="count").to_dict(orient="records")
        )
        failure_timeline = [
            {"time": f"bucket_{int(item['bucket'])}", "count": int(item["count"])}
            for item in failure_timeline
        ]

    root_cause_suggestions = []
    history = df.to_dict(orient="records")
    for _, row in df.iterrows():
        root_cause_suggestions.append(
            {
                "failure_id": int(row["id"]),
                "module": row["module"],
                "category": row["category"],
                "suggestion": ROOT_CAUSE_MAP.get(row["category"], "Investigate failure context"),
                "causal_score": estimate_causal_score(row, history),
            }
        )

    debug_recommendations = [
        {
            "failure_id": int(row["id"]),
            "recommendation": RECOMMEND_MAP.get(row["category"], "Inspect surrounding signals and logs"),
        }
        for _, row in df.iterrows()
    ]

    new_failure_count = int((df["first_seen_run_id"] == run_id).sum()) if "first_seen_run_id" in df else 0
    known_failure_count = max(int(len(df) - new_failure_count), 0)
    recurrence_rate = round((known_failure_count / len(df)) * 100.0, 2) if len(df) else 0.0

    if "closed_at" in df and "first_seen_at" in df:
        df["closed_at"] = pd.to_datetime(df["closed_at"], errors="coerce")
        df["first_seen_at"] = pd.to_datetime(df["first_seen_at"], errors="coerce")
        closed_rows = df[df["closed_at"].notna() & df["first_seen_at"].notna()]
    else:
        closed_rows = pd.DataFrame()
    if not closed_rows.empty:
        durations = (closed_rows["closed_at"] - closed_rows["first_seen_at"]).dt.total_seconds() / 3600.0
        mttr_hours = round(float(durations.mean()), 2)
    else:
        mttr_hours = None

    status_breakdown = (
        df["status"].fillna("open").value_counts().reset_index().rename(columns={"index": "status", "status": "count"})
        .to_dict(orient="records")
    )

    trend_vs_prev_run = None
    all_runs = get_runs(user_id=user["user_id"])
    prev = None
    for idx, r in enumerate(all_runs):
        if r["_id"] == run_id and idx + 1 < len(all_runs):
            prev = all_runs[idx + 1]
            break
    if prev:
        prev_score = prev.get("health_score", 0)
        curr_score = run.get("health_score", 0)
        if curr_score > prev_score:
            trend_vs_prev_run = "improving"
        elif curr_score < prev_score:
            trend_vs_prev_run = "regressing"
        else:
            trend_vs_prev_run = "stable"

    coords_available = all(
        f.get("cluster_x") is not None and f.get("cluster_y") is not None for f in failures
    )
    if coords_available:
        cluster_points = [
            {
                "cluster_id": int(f.get("cluster_id", 0)),
                "x": float(f.get("cluster_x", 0.0)),
                "y": float(f.get("cluster_y", 0.0)),
                "size": 1,
            }
            for f in failures
        ]
    else:
        embeddings = generate_embeddings(
            df["message"].tolist(),
            EmbeddingConfig(use_longformer=len(df) > 2000),
        )
        if len(df) >= 2:
            pca = PCA(n_components=2)
            coords = pca.fit_transform(embeddings)
        else:
            coords = [[0.0, 0.0]]
        cluster_points = []
        for idx, row in df.iterrows():
            cluster_points.append(
                {
                    "cluster_id": int(row["cluster_id"]),
                    "x": float(coords[idx][0]),
                    "y": float(coords[idx][1]),
                    "size": 1,
                }
            )

    return {
        "health_score": run.get("health_score"),
        "total_failures": run.get("total_failures"),
        "unique_failures": run.get("unique_failures"),
        "critical_count": run.get("critical_count"),
        "category_distribution": category_distribution,
        "module_hotspots": module_hotspots,
        "priority_ranking": priority_ranking,
        "failure_clusters": cluster_points,
        "failure_timeline": failure_timeline,
        "root_cause_suggestions": root_cause_suggestions,
        "debug_recommendations": debug_recommendations,
        "new_failure_count": new_failure_count,
        "known_failure_count": known_failure_count,
        "recurrence_rate": recurrence_rate,
        "mttr_hours": mttr_hours,
        "status_breakdown": status_breakdown,
        "trend_vs_prev_run": trend_vs_prev_run,
    }


@app.get("/failures/{run_id}")
@limiter.limit("60/minute")
def get_failures(
    request: Request,
    run_id: int,
    user: str = Depends(get_current_user),
    limit: Optional[int] = None,
    offset: Optional[int] = None,
):
    if limit is not None and limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be > 0")
    if offset is not None and offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")
    run = get_run(run_id, user_id=user["user_id"])
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    failures = get_failures_by_run(run_id, limit=limit, offset=offset)

    return [
        {
            "id": f["_id"],
            "timestamp": f.get("timestamp"),
            "sim_time": f.get("sim_time"),
            "severity": f.get("severity"),
            "severity_raw": f.get("severity_raw"),
            "failure_type": f.get("failure_type"),
            "module": f.get("module"),
            "line_no": f.get("line_no"),
            "message": f.get("message"),
            "context": f.get("context"),
            "test_name": f.get("test_name"),
            "seed": f.get("seed"),
            "dut_path": f.get("dut_path"),
            "uvm_phase": f.get("uvm_phase"),
            "source_file": f.get("source_file"),
            "source_line": f.get("source_line"),
            "category": f.get("category"),
            "cluster_id": f.get("cluster_id"),
            "cluster_x": f.get("cluster_x"),
            "cluster_y": f.get("cluster_y"),
            "priority_score": f.get("priority_score"),
            "is_duplicate": f.get("is_duplicate"),
            "unique_failure_id": f.get("unique_failure_id"),
            "status": f.get("status"),
            "first_seen_run_id": f.get("first_seen_run_id"),
            "last_seen_run_id": f.get("last_seen_run_id"),
            "first_seen_at": f.get("first_seen_at"),
            "last_seen_at": f.get("last_seen_at"),
            "closed_at": f.get("closed_at"),
        }
        for f in failures
    ]


@app.patch("/failure/{failure_id}/status")
@limiter.limit("60/minute")
def update_failure_status_api(
    request: Request,
    failure_id: int,
    payload: FailureStatusUpdate,
    user: str = Depends(get_current_user),
):
    status_val = payload.status.strip().lower()
    allowed = {"open", "investigating", "closed", "wontfix"}
    if status_val not in allowed:
        raise HTTPException(status_code=400, detail="Invalid status")
    existing = get_failure_by_id(failure_id, user_id=user["user_id"])
    if not existing:
        raise HTTPException(status_code=404, detail="Failure not found")
    updated = update_failure_status(failure_id, status_val, user_id=user["user_id"])
    if not updated:
        raise HTTPException(status_code=404, detail="Failure not found")
    return {
        "id": updated["_id"],
        "status": updated.get("status"),
        "status_updated_at": updated.get("status_updated_at"),
        "closed_at": updated.get("closed_at"),
    }


@app.get("/runs")
@limiter.limit("60/minute")
def list_runs(
    request: Request,
    user: str = Depends(get_current_user),
    limit: Optional[int] = None,
    offset: Optional[int] = None,
):
    if limit is not None and limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be > 0")
    if offset is not None and offset < 0:
        raise HTTPException(status_code=400, detail="offset must be >= 0")

    runs = get_runs(user_id=user["user_id"], limit=limit, offset=offset)

    return [
        {
            "id": r["_id"],
            "filename": r.get("filename"),
            "uploaded_at": r.get("uploaded_at").isoformat(),
            "total_failures": r.get("total_failures"),
            "unique_failures": r.get("unique_failures"),
            "critical_count": r.get("critical_count"),
            "health_score": r.get("health_score"),
        }
        for r in runs
    ]


@app.get("/compare-runs")
@limiter.limit("40/minute")
def compare_runs(
    request: Request,
    run_a: int,
    run_b: int,
    user: str = Depends(get_current_user),
):
    run_a_doc = get_run(run_a, user_id=user["user_id"])
    run_b_doc = get_run(run_b, user_id=user["user_id"])
    if not run_a_doc or not run_b_doc:
        raise HTTPException(status_code=404, detail="Run not found")
    fails_a = get_failures_by_run(run_a)
    fails_b = get_failures_by_run(run_b)
    sig_a = {f.get("signature") for f in fails_a if f.get("signature")}
    sig_b = {f.get("signature") for f in fails_b if f.get("signature")}

    recurring = sig_a.intersection(sig_b)
    new_in_b = sig_b.difference(sig_a)
    resolved_in_b = sig_a.difference(sig_b)

    return {
        "run_a": run_a,
        "run_b": run_b,
        "recurring_count": len(recurring),
        "new_in_b_count": len(new_in_b),
        "resolved_in_b_count": len(resolved_in_b),
        "run_a_totals": {
            "total_failures": run_a_doc.get("total_failures"),
            "unique_failures": run_a_doc.get("unique_failures"),
            "health_score": run_a_doc.get("health_score"),
        },
        "run_b_totals": {
            "total_failures": run_b_doc.get("total_failures"),
            "unique_failures": run_b_doc.get("unique_failures"),
            "health_score": run_b_doc.get("health_score"),
        },
    }


@app.delete("/run/{run_id}")
@limiter.limit("40/minute")
def delete_run_by_id(
    request: Request,
    run_id: int,
    user: str = Depends(get_current_user),
):
    run = get_run(run_id, user_id=user["user_id"])
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    delete_run(run_id, user_id=user["user_id"])
    return {"status": "deleted"}


@app.get("/report/{run_id}")
@limiter.limit("20/minute")
def export_report(
    request: Request,
    run_id: int,
    format: str = "csv",
    user: str = Depends(get_current_user),
):
    if format.lower() != "csv":
        raise HTTPException(status_code=400, detail="Only CSV format supported")

    run = get_run(run_id, user_id=user["user_id"])
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    failures = get_failures_by_run(run_id)

    df = pd.DataFrame([{
        "timestamp": f.get("timestamp"),
        "sim_time": f.get("sim_time"),
        "severity": f.get("severity"),
        "severity_raw": f.get("severity_raw"),
        "failure_type": f.get("failure_type"),
        "module": f.get("module"),
        "line_no": f.get("line_no"),
        "message": f.get("message"),
        "test_name": f.get("test_name"),
        "seed": f.get("seed"),
        "dut_path": f.get("dut_path"),
        "uvm_phase": f.get("uvm_phase"),
        "source_file": f.get("source_file"),
        "source_line": f.get("source_line"),
        "category": f.get("category"),
        "cluster_id": f.get("cluster_id"),
        "priority_score": f.get("priority_score"),
        "is_duplicate": f.get("is_duplicate"),
        "unique_failure_id": f.get("unique_failure_id"),
        "status": f.get("status"),
        "first_seen_run_id": f.get("first_seen_run_id"),
        "last_seen_run_id": f.get("last_seen_run_id"),
        "first_seen_at": f.get("first_seen_at"),
        "last_seen_at": f.get("last_seen_at"),
        "closed_at": f.get("closed_at"),
    } for f in failures])

    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="text/csv")
