from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import List, Dict, Optional
from pathlib import Path
import io
import gzip
import os
import re
import pandas as pd
from pydantic import BaseModel
from sklearn.decomposition import PCA
from dotenv import load_dotenv
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from loguru import logger
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator
import time
import uuid
import jwt
import pika

from nlp.embeddings import generate_embeddings, EmbeddingConfig
from ml.dedup_engine import DedupEngine, DedupConfig
from ml.root_cause_graph import RootCauseAnalyzer
from ml.causal_inference import estimate_causal_score

from parser import parse_logs
from preprocessor import preprocess_records
from categorizer import categorize_messages
from deduplicator import deduplicate
from clusterer import cluster_embeddings
from scorer import (
    MODULE_WEIGHTS,
    SEVERITY_WEIGHTS,
    compute_scores,
    get_current_weights,
    optimize_weights,
    prioritize_failures,
)
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
    delete_all_runs_for_user,
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

# Load env from backend/.env explicitly (works regardless of cwd)
load_dotenv(dotenv_path=(Path(__file__).resolve().parent / ".env"))

SECRET_KEY = os.environ.get("DEBUGIQ_JWT_SECRET", "debugiq_dev_only_secret_change_me")
ALGORITHM = "HS256"
ADMIN_USERNAME = os.environ.get("DEBUGIQ_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("DEBUGIQ_ADMIN_PASSWORD", "admin123")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_mongo()
    # Seed a single fixed admin if none exists.
    if not admin_exists():
        try:
            create_user(ADMIN_USERNAME, hash_password(ADMIN_PASSWORD), "admin")
            logger.info("Seeded initial admin user from environment.")
        except Exception as exc:
            logger.warning("Failed to seed admin user: %s", exc)
    yield


app = FastAPI(title="DebugIQ API", lifespan=lifespan)

_cors_origins_env = os.environ.get("CORS_ALLOWED_ORIGINS", "")
_extra_origins = [origin.strip() for origin in _cors_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        *_extra_origins,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


class RunChatTurn(BaseModel):
    role: str
    content: str


class RunChatRequest(BaseModel):
    message: str
    history: List[RunChatTurn] = []


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


def _to_dataframe(failures: List[Dict]) -> pd.DataFrame:
    return pd.DataFrame(failures)


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


def _run_ids_mentioned_in_chat_message(message: str) -> List[int]:
    ids: List[int] = []
    for pattern in (
        r"(?i)\brun\s+id\s*#?\s*(\d+)",
        r"(?i)\brun\s+#\s*(\d+)",
        r"(?i)\bfor\s+run\s*#?\s*(\d+)",
        r"(?i)\brun\s+(\d+)\b",
    ):
        for m in re.finditer(pattern, message):
            ids.append(int(m.group(1)))
    return ids


def _resolve_chat_context_run_id(message: str, path_run_id: int, user_id: int) -> tuple[int, str]:
    """
    If the user names another run they own (e.g. 'summarize run 12', 'run id 12'),
    use that run's failure list. Last matching mention wins. If a number is not a
    valid run for this user (e.g. typo, or a failure id), keep the URL run and note it.
    """
    candidates = _run_ids_mentioned_in_chat_message(message)
    if not candidates:
        return path_run_id, ""

    for cid in reversed(candidates):
        if get_run(cid, user_id=user_id):
            if cid != path_run_id:
                note = (
                    f"The page is open on run #{path_run_id}, but the user explicitly referenced run #{cid}; "
                    f"the failure list below is for run #{cid} only. Ground answers in that list."
                )
            else:
                note = ""
            return cid, note

    bad = candidates[-1]
    note = (
        f"The user seemed to reference run #{bad}, but that id is not a run on this account (or it was a typo). "
        f"The data below is still for run #{path_run_id}; say so briefly if relevant."
    )
    return path_run_id, note


def _is_general_chat_intent(message: str) -> bool:
    """
    True = answer from general verification knowledge only (no run/failure dump in the system prompt).
    False = ground the reply in run data (current URL run or a run id the user named).
    """
    m = (message or "").strip()
    if not m:
        return True
    if "[User focus:" in m:
        return False
    if _run_ids_mentioned_in_chat_message(m):
        return False
    if re.search(r"(?i)\b(failure|failures|fails)\b", m):
        return False
    if re.search(r"(?i)\bfailure\s*(?:id|#)?\s*\d+", m):
        return False
    if re.search(
        r"(?i)\b(this run|my run|the run|run\s*#|run\s+id|for run|uvm_error|uvm_fatal|uvm_warning|dashboard|upload|log file|summarize|summary|top issues|what went|analyze|list)\b",
        m,
    ):
        return False
    if re.search(r"(?i)\b(summarize|summary|issues|failed|failing|what went)\b", m):
        return False
    if re.search(r"(?i)^(hi|hello|hey|thanks|thank you|ok|okay|yes|no|bye)\s*[\.\!]*$", m):
        return True
    if re.search(
        r"(?i)^(what|how|why|when|explain|define|describe|compare|difference|is it|are there|can you|tell me about)\b",
        m,
    ):
        if re.search(r"(?i)\b(my|this|the)\s+(log|run|test|failure|suite)\b", m):
            return False
        return True
    # Likely module / hierarchy name (e.g. CACHE_CTRL) — ground in run data
    if re.search(r"(?i)(?<![A-Za-z0-9_])[A-Za-z0-9]+_[A-Za-z0-9_]+", m):
        return False
    if len(m) < 80 and not re.search(r"\d", m):
        if not re.search(r"(?i)\b(failure|failures|run|log|uvm|error|module|debug|id)\b", m):
            return True
    return False


def _strip_user_focus_prefix(message: str) -> str:
    return re.sub(r"(?is)^\[User focus:[^\]]+\]\s*", "", message or "").strip()


def _focused_failure_id(message: str) -> int | None:
    match = re.search(r"(?i)\[User focus:\s*failure id\s*=\s*(\d+)", message or "")
    return int(match.group(1)) if match else None


def _is_short_social_message(message: str) -> bool:
    return bool(
        re.search(
            r"(?i)^(hi|hello|hey|thanks|thank you|ok|okay|yes|no|bye)\s*[\.\!]*$",
            (message or "").strip(),
        )
    )


def _truncate_chat_data_block(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return (
        text[: max_chars - 120]
        + "\n\n[Data truncated for length. Ask about a narrower scope or a specific failure/run id.]"
    )


def _format_failures_for_chat_detail(failures: List[Dict], *, max_items: int) -> str:
    lines: List[str] = []
    for i, f in enumerate(failures[:max_items]):
        fid = f.get("_id")
        msg = str(f.get("message") or "")
        ctx = str(f.get("context") or "")
        if len(msg) > 600:
            msg = msg[:600] + "..."
        if len(ctx) > 300:
            ctx = ctx[:300] + "..."
        lines.append(
            f"--- failure index {i + 1} | id={fid} ---\n"
            f"severity: {f.get('severity')}\n"
            f"severity_raw: {f.get('severity_raw')}\n"
            f"module: {f.get('module')}\n"
            f"category: {f.get('category')}\n"
            f"failure_type: {f.get('failure_type')}\n"
            f"timestamp: {f.get('timestamp')}\n"
            f"sim_time: {f.get('sim_time')}\n"
            f"line_no: {f.get('line_no')}\n"
            f"test_name: {f.get('test_name')}\n"
            f"seed: {f.get('seed')}\n"
            f"uvm_phase: {f.get('uvm_phase')}\n"
            f"dut_path: {f.get('dut_path')}\n"
            f"source_file: {f.get('source_file')}\n"
            f"source_line: {f.get('source_line')}\n"
            f"unique_failure_id: {f.get('unique_failure_id')}\n"
            f"message:\n{msg}\n"
            f"context:\n{ctx}\n"
        )
    return "\n".join(lines) if lines else "(no failures in this run)"


@app.post("/chat/run/{run_id}")
@limiter.limit("30/minute")
def api_run_chat(
    request: Request,
    run_id: int,
    body: RunChatRequest,
    user: str = Depends(get_current_user),
):
    run = get_run(run_id, user_id=user["user_id"])
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    user_turns: List[str] = []
    for turn in body.history[-12:]:
        if (turn.role or "").strip().lower() == "user" and (turn.content or "").strip():
            user_turns.append(turn.content.strip())
    user_turns.append((body.message or "").strip())
    combined_user_text = "\n".join(user_turns)

    last_msg = (body.message or "").strip()
    clean_last_msg = _strip_user_focus_prefix(last_msg)
    focus_failure_id = _focused_failure_id(last_msg)
    use_general = _is_general_chat_intent(clean_last_msg) and (
        focus_failure_id is None or _is_short_social_message(clean_last_msg)
    )

    from ml.explainability import generate_llm_chat

    if use_general:
        system = (
            "You are DebugIQ's assistant for hardware verification, SystemVerilog, UVM, and SVA. "
            "Answer from general engineering knowledge only. The user did not ask for analysis of a specific "
            "uploaded run or failure list—do not invent log lines, failure ids, or run-specific data."
        )
        msgs: List[Dict[str, str]] = [{"role": "system", "content": system}]
        for turn in body.history[-20:]:
            role = (turn.role or "").strip().lower()
            if role not in {"user", "assistant"} or not (turn.content or "").strip():
                continue
            msgs.append({"role": role, "content": turn.content.strip()})
        msgs.append({"role": "user", "content": clean_last_msg})
        try:
            reply = generate_llm_chat(msgs)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"LLM provider error: {str(exc)}") from exc
        return {"reply": reply, "context_run_id": None, "chat_mode": "general"}

    context_run_id, context_note = _resolve_chat_context_run_id(
        combined_user_text, run_id, user["user_id"]
    )
    context_run = get_run(context_run_id, user_id=user["user_id"])
    max_failures = int(os.environ.get("CHAT_RUN_MAX_FAILURES", "30"))
    max_block_chars = int(os.environ.get("CHAT_RUN_DATA_MAX_CHARS", "6000"))
    failures = get_failures_by_run(context_run_id)
    prompt_failures = failures
    if focus_failure_id is not None:
        focused = [f for f in failures if int(f.get("_id", -1)) == focus_failure_id]
        if focused:
            prompt_failures = focused
            max_failures = 1
    block = _format_failures_for_chat_detail(prompt_failures, max_items=max_failures)
    block = _truncate_chat_data_block(block, max_block_chars)
    fname = (context_run or {}).get("filename") or "unknown"
    total_f = len(failures)

    system_parts = [
        "You are DebugIQ's assistant for hardware verification and simulation/UVM logs. "
        "The user asked for run-grounded help: use ONLY the run metadata and failure records below.",
        f"The dashboard URL run is #{run_id}. The data below describes run #{context_run_id} "
        f"(log file: {fname}; {total_f} failure row(s) in DB; {len(prompt_failures[:max_failures])} included in this prompt).",
        "Answer using these records: quote failure ids, modules, severities, categories, and message/context text. "
        "Give concrete next steps tied to those lines. If something is not in the data, say so.",
    ]

    try:
        reply = generate_llm_chat(msgs)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"LLM provider error: {str(exc)}") from exc
    return {"reply": reply, "context_run_id": context_run_id, "chat_mode": "run"}


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
    try:
        _publish_upload_job(job["_id"])
    except Exception as exc:
        logger.warning(
            "RabbitMQ publish failed (job queued in DB, worker may not be running): %s",
            exc,
        )
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

    total_rows = len(df)
    module_efficiency: List[Dict] = []
    for mod, cnt in module_counts.items():
        c = int(cnt)
        eff = (
            round(100.0 * (1.0 - float(c) / float(total_rows)), 1)
            if total_rows
            else 100.0
        )
        module_efficiency.append(
            {"module": mod, "error_count": c, "efficiency": eff}
        )
    module_efficiency.sort(key=lambda x: (-x["efficiency"], str(x["module"])))

    freq_map = df["unique_failure_id"].value_counts().to_dict()

    priority_ranking = (
        df.sort_values("priority_score", ascending=False)
        .assign(rank=lambda d: range(1, len(d) + 1))
        [["rank", "severity", "module", "category", "priority_score", "unique_failure_id"]]
        .rename(columns={"priority_score": "score"})
        .assign(frequency=lambda d: d["unique_failure_id"].map(freq_map))
        .to_dict(orient="records")
    )

    def _timeline_by_row_index(n: int) -> List[Dict]:
        target_bins = 24
        bucket_size = max(1, (n + target_bins - 1) // target_bins)
        idx_df = pd.DataFrame({"bucket": [i // bucket_size for i in range(n)]})
        rows = idx_df.groupby("bucket").size().reset_index(name="count").to_dict(orient="records")
        return [
            {"time": f"part_{int(item['bucket']) + 1}", "count": int(item["count"])}
            for item in rows
        ]

    # Build an adaptive timeline histogram. If timestamps collapse into one
    # bucket, use log-order buckets so the chart still shows progression.
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
        if len(failure_timeline) <= 1 and len(df) > 1:
            failure_timeline = _timeline_by_row_index(len(df))
    else:
        failure_timeline = _timeline_by_row_index(len(df))

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
        "module_efficiency": module_efficiency,
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


@app.delete("/runs")
@limiter.limit("10/minute")
def clear_all_runs(request: Request, user: str = Depends(get_current_user)):
    summary = delete_all_runs_for_user(user_id=user["user_id"])
    return summary


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
