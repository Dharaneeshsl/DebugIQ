from __future__ import annotations

import os
from typing import Dict, List, Optional
from datetime import datetime

from pymongo import MongoClient, ASCENDING, ReturnDocument
from dotenv import load_dotenv
from pathlib import Path
from pymongo.collection import Collection

# Load env from backend/.env explicitly (works regardless of cwd)
load_dotenv(dotenv_path=(Path(__file__).resolve().parent / ".env"))

_client: MongoClient | None = None


def _get_client() -> MongoClient:
    global _client
    if _client is None:
        mongo_uri = os.environ.get("MONGO_URI")
        if mongo_uri:
            mongo_uri = mongo_uri.strip()
        if not mongo_uri:
            raise RuntimeError("MONGO_URI is not set")
        _client = MongoClient(mongo_uri)
    return _client


def _db():
    db_name = os.environ.get("MONGO_DB_NAME", "debugiq").strip() or "debugiq"
    return _get_client()[db_name]


def _counters() -> Collection:
    return _db()["counters"]


def _next_id(name: str) -> int:
    doc = _counters().find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(doc["seq"])


def init_mongo() -> None:
    db = _db()
    db["users"].create_index([("username", ASCENDING)], unique=True)
    db["runs"].create_index([("user_id", ASCENDING), ("uploaded_at", ASCENDING)])
    db["failures"].create_index([("run_id", ASCENDING)])
    db["upload_jobs"].create_index([("user_id", ASCENDING), ("created_at", ASCENDING)])
    db["revoked_tokens"].create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
    db["settings"].create_index([("_id", ASCENDING)], unique=True)


# Users
def create_user(username: str, password_hash: str, role: str) -> Dict:
    user_id = _next_id("users")
    doc = {
        "_id": user_id,
        "username": username,
        "password_hash": password_hash,
        "role": role,
        "created_at": datetime.utcnow(),
    }
    _db()["users"].insert_one(doc)
    return doc


def get_user_by_username(username: str) -> Optional[Dict]:
    return _db()["users"].find_one({"username": username})


def admin_exists() -> bool:
    return _db()["users"].find_one({"role": "admin"}) is not None


# Runs + Failures
def create_run(
    filename: str,
    total: int,
    unique: int,
    critical: int,
    health: float,
    *,
    user_id: int | None = None,
) -> Dict:
    run_id = _next_id("runs")
    doc = {
        "_id": run_id,
        "filename": filename,
        "uploaded_at": datetime.utcnow(),
        "total_failures": total,
        "unique_failures": unique,
        "critical_count": critical,
        "health_score": health,
        "user_id": user_id,
    }
    _db()["runs"].insert_one(doc)
    return doc


def add_failures(run_id: int, failures: List[dict]) -> None:
    if not failures:
        return
    docs = []
    for f in failures:
        fail_id = _next_id("failures")
        docs.append(
            {
                "_id": fail_id,
                "run_id": run_id,
                "timestamp": f.get("timestamp"),
                "severity": f.get("severity"),
                "module": f.get("module"),
                "line_no": f.get("line_no"),
                "message": f.get("message"),
                "context": f.get("context"),
                "category": f.get("category"),
                "cluster_id": f.get("cluster_id"),
                "cluster_x": f.get("cluster_x"),
                "cluster_y": f.get("cluster_y"),
                "priority_score": f.get("priority_score"),
                "is_duplicate": f.get("is_duplicate"),
                "unique_failure_id": f.get("unique_failure_id"),
            }
        )
    _db()["failures"].insert_many(docs)


def get_run(run_id: int, *, user_id: int | None = None) -> Optional[Dict]:
    q = {"_id": run_id}
    if user_id is not None:
        q["user_id"] = user_id
    return _db()["runs"].find_one(q)


def get_runs(*, user_id: int | None = None, limit: int | None = None, offset: int | None = None) -> List[Dict]:
    q = {}
    if user_id is not None:
        q["user_id"] = user_id
    cursor = _db()["runs"].find(q).sort("uploaded_at", -1)
    if offset:
        cursor = cursor.skip(int(offset))
    if limit:
        cursor = cursor.limit(int(limit))
    return list(cursor)


def get_failures_by_run(run_id: int, *, limit: int | None = None, offset: int | None = None) -> List[Dict]:
    cursor = _db()["failures"].find({"run_id": run_id})
    if offset:
        cursor = cursor.skip(int(offset))
    if limit:
        cursor = cursor.limit(int(limit))
    return list(cursor)


def delete_run(run_id: int, *, user_id: int | None = None) -> None:
    q = {"_id": run_id}
    if user_id is not None:
        q["user_id"] = user_id
    run = _db()["runs"].find_one(q)
    if not run:
        return
    _db()["runs"].delete_one({"_id": run_id})
    _db()["failures"].delete_many({"run_id": run_id})


def get_history_counts(*, user_id: int | None = None) -> dict:
    q = {}
    if user_id is not None:
        # Fetch run_ids for this user to scope history
        run_ids = [r["_id"] for r in _db()["runs"].find({"user_id": user_id}, {"_id": 1})]
        if not run_ids:
            return {}
        q = {"run_id": {"$in": run_ids}}
    results = _db()["failures"].find(q, {"module": 1, "category": 1})
    counts: dict = {}
    for row in results:
        key = f"{row.get('module')}:{row.get('category')}"
        counts[key] = counts.get(key, 0) + 1
    return counts


def get_weights() -> Optional[Dict[str, float]]:
    doc = _db()["settings"].find_one({"_id": "priority_weights"})
    return doc.get("weights") if doc else None


def set_weights(weights: Dict[str, float]) -> None:
    _db()["settings"].update_one(
        {"_id": "priority_weights"},
        {"$set": {"weights": weights, "updated_at": datetime.utcnow()}},
        upsert=True,
    )


# Upload jobs
def create_upload_job(filename: str, raw_logs_text: str, *, user_id: int | None = None) -> Dict:
    job_id = _next_id("upload_jobs")
    doc = {
        "_id": job_id,
        "created_at": datetime.utcnow(),
        "filename": filename,
        "raw_logs_text": raw_logs_text,
        "status": "queued",
        "error": None,
        "run_id": None,
        "user_id": user_id,
        "retry_count": 0,
        "max_retries": 2,
    }
    _db()["upload_jobs"].insert_one(doc)
    return doc


def get_upload_job(job_id: int, *, user_id: int | None = None) -> Optional[Dict]:
    q = {"_id": job_id}
    if user_id is not None:
        q["user_id"] = user_id
    return _db()["upload_jobs"].find_one(q)


def increment_upload_job_retry(job_id: int) -> int:
    doc = _db()["upload_jobs"].find_one_and_update(
        {"_id": job_id},
        {"$inc": {"retry_count": 1}},
        return_document=ReturnDocument.AFTER,
    )
    return int(doc.get("retry_count", 0)) if doc else 0


def set_upload_job_status(
    job_id: int,
    status: str,
    *,
    error: Optional[str] = None,
    run_id: Optional[int] = None,
) -> None:
    update: Dict = {"status": status}
    if error is not None:
        update["error"] = error
    if run_id is not None:
        update["run_id"] = run_id
    _db()["upload_jobs"].update_one({"_id": job_id}, {"$set": update})


def revoke_token(jti: str, exp_ts: int) -> None:
    expires_at = datetime.utcfromtimestamp(int(exp_ts))
    _db()["revoked_tokens"].update_one(
        {"_id": jti},
        {"$set": {"expires_at": expires_at}},
        upsert=True,
    )


def is_token_revoked(jti: str) -> bool:
    if not jti:
        return False
    doc = _db()["revoked_tokens"].find_one({"_id": jti})
    return doc is not None
