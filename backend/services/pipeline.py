from __future__ import annotations

from typing import Dict

from parser import parse_logs
from preprocessor import preprocess_records
from categorizer import categorize_messages
from deduplicator import deduplicate
from clusterer import cluster_embeddings
from scorer import compute_scores

from mongo_store import (
    create_run,
    add_failures,
    get_history_counts,
)


def process_log_text(text: str, filename: str, *, user_id: int | None = None) -> Dict:
    """
    Main log->failures->ML pipeline.
    Shared by synchronous API and the async RabbitMQ worker.
    """
    parsed = parse_logs(text)
    if not parsed:
        raise ValueError("No valid log lines found")

    messages = [p["message"] for p in parsed]
    preprocessed = preprocess_records(messages)
    categories = categorize_messages(messages)
    unique_ids, is_duplicate, embeddings = deduplicate(preprocessed)
    cluster_ids, _cluster_points = cluster_embeddings(embeddings)

    history_counts = get_history_counts(user_id=user_id)

    history_keys = [f"{p['module']}:{categories[idx]}" for idx, p in enumerate(parsed)]
    scores, _freq_map = compute_scores(
        [p["severity"] for p in parsed],
        [p["module"] for p in parsed],
        unique_ids,
        history_keys=history_keys,
        history_counts=history_counts,
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
    unique = len(set(unique_ids)) if unique_ids else 0
    critical = sum(1 for f in failures if f["severity"] == "FATAL")

    # Regression health: penalize duplicates; keep it simple for v1
    if total == 0:
        health = 100.0
    else:
        health = round(max(100.0 - (unique / total * 100.0), 0.0), 2)

    run = create_run(filename, total, unique, critical, health, user_id=user_id)
    run_id = run["_id"]
    add_failures(run_id, failures)

    return {
        "run_id": run_id,
        "total_failures": total,
        "unique_failures": unique,
        "critical_count": critical,
        "health_score": health,
    }

