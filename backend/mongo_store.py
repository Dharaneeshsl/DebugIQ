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


def get_runs(*, user_id: int | None = None) -> List[Dict]:
    q = {}
    if user_id is not None:
        q["user_id"] = user_id
    return list(_db()["runs"].find(q).sort("uploaded_at", -1))


def get_failures_by_run(run_id: int) -> List[Dict]:
    return list(_db()["failures"].find({"run_id": run_id}))


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
    }
    _db()["upload_jobs"].insert_one(doc)
    return doc


def get_upload_job(job_id: int, *, user_id: int | None = None) -> Optional[Dict]:
    q = {"_id": job_id}
    if user_id is not None:
        q["user_id"] = user_id
    return _db()["upload_jobs"].find_one(q)


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
