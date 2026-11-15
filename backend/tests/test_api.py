"""Exercise the real API and persistent local store without external services."""
import gzip
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DEBUGIQ_STORAGE", "sqlite")
    monkeypatch.setenv("DEBUGIQ_SQLITE_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("DEBUGIQ_EMBEDDINGS_BACKEND", "tfidf")
    monkeypatch.delenv("RABBITMQ_URL", raising=False)
    from main import app, limiter
    limiter.enabled = False
    with TestClient(app) as api:
        yield api
    limiter.enabled = True


def auth(client, username="tester"):
    response = client.post("/signup", json={"username": username, "password": "test-password-123", "role": "user"})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


LOG = "[12:00:00.100] ERROR CPU line 10 UVM_ERROR: instruction fetch timeout\n"


def upload(client, headers, text=LOG):
    response = client.post("/upload", headers=headers, files={"file": ("sample.log", text)})
    assert response.status_code == 200, response.text
    return response.json()["run_id"]


def test_complete_user_flow(client, monkeypatch):
    headers = auth(client)
    run_id = upload(client, headers)
    dashboard = client.get(f"/dashboard/{run_id}", headers=headers)
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["total_failures"] == 1
    assert dashboard.json()["failure_timeline"] == [{"time": "12:00:00", "count": 1}]
    assert dashboard.json()["status_breakdown"] == [{"status": "open", "count": 1}]
    failure = client.get(f"/failures/{run_id}", headers=headers).json()[0]
    status = client.patch(f"/failure/{failure['id']}/status", headers=headers, json={"status": "closed"})
    assert status.status_code == 200, status.text
    assert client.get(f"/dashboard/{run_id}", headers=headers).json()["mttr_hours"] is not None
    from ml import explainability
    monkeypatch.setattr(explainability, "generate_llm_explanation", lambda _: (_ for _ in ()).throw(RuntimeError("offline")))
    monkeypatch.setattr(explainability, "generate_llm_chat", lambda _: (_ for _ in ()).throw(RuntimeError("offline")))
    explanation = client.get(f"/explain/{run_id}/{failure['id']}", headers=headers)
    assert explanation.status_code == 200, explanation.text
    assert explanation.json()["source"] == "local_rules"
    chat = client.post(f"/chat/run/{run_id}", headers=headers, json={"message": "summarize this run"})
    assert chat.status_code == 200 and "Local analysis" in chat.json()["reply"]
    report = client.get(f"/report/{run_id}", headers=headers)
    assert report.status_code == 200 and "attachment" in report.headers["content-disposition"]
    assert "instruction fetch timeout" in report.text
    second = upload(client, headers)
    comparison = client.get(f"/compare-runs?run_a={run_id}&run_b={second}", headers=headers)
    assert comparison.json()["recurring_count"] == 1
    assert client.delete(f"/run/{run_id}", headers=headers).status_code == 200
    assert client.get(f"/dashboard/{run_id}", headers=headers).status_code == 404
    assert client.delete("/runs", headers=headers).json()["deleted_runs"] == 1
    assert client.post("/logout", headers=headers).status_code == 200
    assert client.get("/runs", headers=headers).status_code == 401


def test_user_isolation_and_roles(client):
    owner = auth(client, "owner")
    other = auth(client, "other")
    run_id = upload(client, owner)
    failure = client.get(f"/failures/{run_id}", headers=owner).json()[0]
    for path in (f"/dashboard/{run_id}", f"/failures/{run_id}", f"/report/{run_id}"):
        assert client.get(path, headers=other).status_code == 404
        assert client.get(path).status_code == 401
    assert client.patch(f"/failure/{failure['id']}/status", headers=other, json={"status": "closed"}).status_code == 404
    assert client.delete(f"/run/{run_id}", headers=other).status_code == 404
    assert client.post("/prioritize", headers=other, json={"feedback": []}).status_code == 403


def test_async_and_upload_validation(client, monkeypatch):
    headers = auth(client)
    response = client.post("/upload-async", headers=headers, files={"file": ("sample.log.gz", gzip.compress(LOG.encode()))})
    assert response.status_code == 200, response.text
    job = client.get(f"/job-status/{response.json()['job_id']}", headers=headers).json()
    assert job["status"] == "completed" and job["run_id"]
    for filename, content in [("bad.gz", b"broken"), ("empty.log", b""), ("bad.exe", b"content")]:
        assert client.post("/upload", headers=headers, files={"file": (filename, content)}).status_code == 400
    monkeypatch.setenv("DEBUGIQ_MAX_UPLOAD_BYTES", "64")
    for name, value in [("big.log", b"x" * 65), ("big.gz", gzip.compress(b"x" * 1000))]:
        assert client.post("/upload", headers=headers, files={"file": (name, value)}).status_code == 413


def test_store_persistence_and_atomic_counters(client):
    from mongo_store import _next_id, get_user_by_username
    auth(client)
    assert get_user_by_username("tester")["role"] == "user"
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(lambda _: _next_id("concurrent"), range(20)))
    assert sorted(ids) == list(range(1, 21))
    from mongo_store import create_upload_job, fail_interrupted_local_jobs, get_upload_job
    job = create_upload_job("interrupted.log", LOG)
    fail_interrupted_local_jobs()
    assert get_upload_job(job["_id"])["status"] == "failed"


def test_signup_validation(client):
    assert client.post("/signup", json={"username": "", "password": "x"}).status_code == 422
    auth(client)
    assert client.post("/signup", json={"username": "tester", "password": "test-password-123"}).status_code == 400


def test_duplicate_ranking_and_queue_failure(client, monkeypatch):
    headers = auth(client)
    run_id = upload(client, headers, LOG + LOG.replace("12:00:00.100", "12:00:02.100"))
    dashboard = client.get(f"/dashboard/{run_id}", headers=headers).json()
    assert dashboard["total_failures"] == 2 and dashboard["unique_failures"] == 1
    assert len(dashboard["priority_ranking"]) == 1
    assert dashboard["priority_ranking"][0]["frequency"] == 2
    monkeypatch.setenv("RABBITMQ_URL", "amqp://unavailable")
    import main
    def unavailable(_):
        raise ConnectionError("queue offline")
    monkeypatch.setattr(main, "_publish_upload_job", unavailable)
    assert client.post("/upload-async", headers=headers, files={"file": ("demo.log", LOG)}).status_code == 503


def test_untimed_assertions_do_not_distort_timeline(client):
    headers = auth(client)
    run_id = upload(client, headers, LOG + "ASSERTION FAILED: axi_valid_stable at axi_intf.sv:142\n")
    timeline = client.get(f"/dashboard/{run_id}", headers=headers).json()["failure_timeline"]
    assert timeline == [{"time": "12:00:00", "count": 1}, {"time": "No timestamp", "count": 1}]
