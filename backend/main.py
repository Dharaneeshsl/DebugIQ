from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import List, Dict
from pathlib import Path
import io
import gzip
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.decomposition import PCA

from parser import parse_logs
from preprocessor import preprocess_records
from categorizer import categorize_messages
from deduplicator import deduplicate
from clusterer import cluster_embeddings
from scorer import compute_scores
from database import (
    init_db,
    SessionLocal,
    create_run,
    add_failures,
    get_run,
    get_runs,
    get_failures_by_run,
    delete_run,
)

app = FastAPI(title="DebugIQ API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT_CAUSE_MAP = {
    "assertion_failure": "Possible cause: violated design assumption; inspect surrounding signals",
    "timeout_error": "Possible cause: clock domain issue or stalled handshake",
    "protocol_violation": "Possible cause: incorrect sequencing; verify FSM transitions",
    "data_mismatch": "Possible cause: pipeline stage data corruption; check write-back logic",
    "memory_error": "Possible cause: address decode failure or ECC mismatch",
}

RECOMMEND_MAP = {
    "assertion_failure": "Inspect assertion conditions and triggering signals; validate channel ordering and ready/valid behavior",
    "timeout_error": "Check clock gating logic; verify handshake completion signals",
    "protocol_violation": "Review FSM state transitions; validate protocol sequencing",
    "data_mismatch": "Trace data path; check pipeline registers and write-back stages",
    "memory_error": "Verify address decoder; check ECC logic and memory interface",
}

_model = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


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


def _health_score(total: int, unique: int) -> float:
    if total == 0:
        return 100.0
    score = 100.0 - (unique / total * 100.0)
    return round(max(score, 0.0), 2)


def _to_dataframe(failures: List[Dict]) -> pd.DataFrame:
    return pd.DataFrame(failures)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload")
def upload_log(file: UploadFile = File(...)):
    text = _read_upload(file)
    parsed = parse_logs(text)
    if not parsed:
        raise HTTPException(status_code=400, detail="No valid log lines found")

    messages = [p["message"] for p in parsed]
    preprocessed = preprocess_records(messages)
    categories = categorize_messages(messages)
    unique_ids, is_duplicate, embeddings = deduplicate(preprocessed)
    cluster_ids, cluster_points = cluster_embeddings(embeddings)

    scores, freq_map = compute_scores(
        [p["severity"] for p in parsed],
        [p["module"] for p in parsed],
        unique_ids,
    )

    failures = []
    for idx, p in enumerate(parsed):
        failures.append(
            {
                **p,
                "category": categories[idx],
                "cluster_id": cluster_ids[idx],
                "priority_score": scores[idx],
                "is_duplicate": bool(is_duplicate[idx]),
                "unique_failure_id": unique_ids[idx],
            }
        )

    total = len(failures)
    unique = len(set(unique_ids))
    critical = sum(1 for f in failures if f["severity"] == "FATAL")
    health = _health_score(total, unique)

    session = SessionLocal()
    try:
        run = create_run(session, file.filename, total, unique, critical, health)
        add_failures(session, run.id, failures)
    finally:
        session.close()

    return {
        "run_id": run.id,
        "total_failures": total,
        "unique_failures": unique,
        "critical_count": critical,
        "health_score": health,
    }


@app.get("/dashboard/{run_id}")
def get_dashboard(run_id: int):
    session = SessionLocal()
    try:
        run = get_run(session, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        failures = get_failures_by_run(session, run_id)
    finally:
        session.close()

    if not failures:
        raise HTTPException(status_code=404, detail="No failures found")

    df = pd.DataFrame([{
        "id": f.id,
        "timestamp": f.timestamp,
        "severity": f.severity,
        "module": f.module,
        "line_no": f.line_no,
        "message": f.message,
        "category": f.category,
        "cluster_id": f.cluster_id,
        "priority_score": f.priority_score,
        "is_duplicate": f.is_duplicate,
        "unique_failure_id": f.unique_failure_id,
    } for f in failures])

    category_distribution = (
        df["category"].value_counts().reset_index().rename(columns={"index": "category", "category": "count"})
        .to_dict(orient="records")
    )

    module_hotspots = (
        df["module"].value_counts().reset_index().rename(columns={"index": "module", "module": "count"})
        .to_dict(orient="records")
    )

    freq_map = df["unique_failure_id"].value_counts().to_dict()

    priority_ranking = (
        df.sort_values("priority_score", ascending=False)
        .assign(rank=lambda d: range(1, len(d) + 1))
        [["rank", "severity", "module", "category", "priority_score", "unique_failure_id"]]
        .rename(columns={"priority_score": "score"})
        .assign(frequency=lambda d: d["unique_failure_id"].map(freq_map))
        .to_dict(orient="records")
    )

    failure_timeline = (
        df.groupby("timestamp").size().reset_index(name="count")
        .rename(columns={"timestamp": "time"})
        .to_dict(orient="records")
    )

    root_cause_suggestions = [
        {
            "failure_id": int(row["id"]),
            "module": row["module"],
            "category": row["category"],
            "suggestion": ROOT_CAUSE_MAP.get(row["category"], "Investigate failure context"),
        }
        for _, row in df.iterrows()
    ]

    debug_recommendations = [
        {
            "failure_id": int(row["id"]),
            "recommendation": RECOMMEND_MAP.get(row["category"], "Inspect surrounding signals and logs"),
        }
        for _, row in df.iterrows()
    ]

    model = _get_model()
    embeddings = model.encode(df["message"].tolist(), normalize_embeddings=True)
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
        "health_score": run.health_score,
        "total_failures": run.total_failures,
        "unique_failures": run.unique_failures,
        "critical_count": run.critical_count,
        "category_distribution": category_distribution,
        "module_hotspots": module_hotspots,
        "priority_ranking": priority_ranking,
        "failure_clusters": cluster_points,
        "failure_timeline": failure_timeline,
        "root_cause_suggestions": root_cause_suggestions,
        "debug_recommendations": debug_recommendations,
    }


@app.get("/failures/{run_id}")
def get_failures(run_id: int):
    session = SessionLocal()
    try:
        run = get_run(session, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        failures = get_failures_by_run(session, run_id)
    finally:
        session.close()

    return [
        {
            "id": f.id,
            "timestamp": f.timestamp,
            "severity": f.severity,
            "module": f.module,
            "line_no": f.line_no,
            "message": f.message,
            "category": f.category,
            "cluster_id": f.cluster_id,
            "priority_score": f.priority_score,
            "is_duplicate": f.is_duplicate,
            "unique_failure_id": f.unique_failure_id,
        }
        for f in failures
    ]


@app.get("/runs")
def list_runs():
    session = SessionLocal()
    try:
        runs = get_runs(session)
    finally:
        session.close()

    return [
        {
            "id": r.id,
            "filename": r.filename,
            "uploaded_at": r.uploaded_at.isoformat(),
            "total_failures": r.total_failures,
            "unique_failures": r.unique_failures,
            "critical_count": r.critical_count,
            "health_score": r.health_score,
        }
        for r in runs
    ]


@app.delete("/run/{run_id}")
def delete_run_by_id(run_id: int):
    session = SessionLocal()
    try:
        run = get_run(session, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        delete_run(session, run_id)
    finally:
        session.close()
    return {"status": "deleted"}


@app.get("/report/{run_id}")
def export_report(run_id: int, format: str = "csv"):
    if format.lower() != "csv":
        raise HTTPException(status_code=400, detail="Only CSV format supported")

    session = SessionLocal()
    try:
        run = get_run(session, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        failures = get_failures_by_run(session, run_id)
    finally:
        session.close()

    df = pd.DataFrame([{
        "timestamp": f.timestamp,
        "severity": f.severity,
        "module": f.module,
        "line_no": f.line_no,
        "message": f.message,
        "category": f.category,
        "cluster_id": f.cluster_id,
        "priority_score": f.priority_score,
        "is_duplicate": f.is_duplicate,
        "unique_failure_id": f.unique_failure_id,
    } for f in failures])

    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="text/csv")
