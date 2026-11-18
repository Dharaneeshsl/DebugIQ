import sqlite3
import pytest
from runtime_config import validate_production
from backup_store import backup


def test_production_rejects_demo_configuration(monkeypatch):
    monkeypatch.setenv("DEBUGIQ_ENV", "production")
    monkeypatch.setenv("DEBUGIQ_JWT_SECRET", "short")
    with pytest.raises(RuntimeError, match="SECRET"):
        validate_production()
    monkeypatch.setenv("DEBUGIQ_JWT_SECRET", "a" * 64)
    monkeypatch.setenv("DEBUGIQ_ADMIN_PASSWORD", "admin123")
    with pytest.raises(RuntimeError, match="PASSWORD"):
        validate_production()
    monkeypatch.setenv("DEBUGIQ_ADMIN_PASSWORD", "random-password-for-testing-only")
    validate_production()


def test_external_ai_requires_explicit_opt_in(monkeypatch):
    from ml.explainability import generate_llm_explanation, generate_llm_chat
    monkeypatch.delenv("DEBUGIQ_ALLOW_EXTERNAL_AI", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    with pytest.raises(RuntimeError, match="privacy"):
        generate_llm_explanation({"message": "private chip log"})
    with pytest.raises(RuntimeError, match="privacy"):
        generate_llm_chat([{"role": "user", "content": "private chip log"}])


def test_backup_restore_round_trip(tmp_path):
    source, copy, restored = [tmp_path / name for name in ("source.db", "backup.db", "restored.db")]
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE records (value TEXT)")
        connection.execute("INSERT INTO records VALUES ('test evidence')")
    backup(source, copy)
    backup(copy, restored)
    with sqlite3.connect(restored) as connection:
        assert connection.execute("SELECT value FROM records").fetchone()[0] == "test evidence"
    with pytest.raises(ValueError):
        backup(copy, restored)


def test_production_api_controls(tmp_path, monkeypatch):
    monkeypatch.setenv("DEBUGIQ_ENV", "production")
    monkeypatch.setenv("DEBUGIQ_JWT_SECRET", "a" * 64)
    monkeypatch.setenv("DEBUGIQ_ADMIN_PASSWORD", "random-password-for-testing-only")
    monkeypatch.setenv("DEBUGIQ_STORAGE", "sqlite")
    monkeypatch.setenv("DEBUGIQ_SQLITE_PATH", str(tmp_path / "company.db"))
    monkeypatch.setenv("DEBUGIQ_SERVE_UI", "false")
    from main import app
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        response = client.get("/api/ready")
        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Request-ID"]
        assert client.post("/api/signup", json={"username": "intruder", "password": "12345678"}).status_code == 403
        assert client.get("/api/public-config").json() == {"signup_enabled": False}


def test_account_changes_revoke_existing_sessions(tmp_path, monkeypatch):
    from auth_utils import hash_password
    from fastapi.testclient import TestClient
    from main import app
    from mongo_store import change_user_access, create_user

    monkeypatch.setenv("DEBUGIQ_STORAGE", "sqlite")
    monkeypatch.setenv("DEBUGIQ_SQLITE_PATH", str(tmp_path / "company.db"))
    initial = {"username": "engineer", "password": "initial-password-123"}
    with TestClient(app) as client:
        create_user(initial["username"], hash_password(initial["password"]), "user")

        def authentication(credentials):
            response = client.post("/token", data=credentials)
            assert response.status_code == 200
            return {"Authorization": "Bearer " + response.json()["access_token"]}

        session = authentication(initial)
        assert client.get("/runs", headers=session).status_code == 200
        assert change_user_access(initial["username"], disabled=True)
        assert client.get("/runs", headers=session).status_code == 401
        assert client.post("/token", data=initial).status_code == 400
        assert change_user_access(initial["username"], disabled=False)
        assert client.get("/runs", headers=session).status_code == 401
        session = authentication(initial)
        replacement = {**initial, "password": "replacement-password-123"}
        assert change_user_access(initial["username"], password_hash=hash_password(replacement["password"]))
        assert client.get("/runs", headers=session).status_code == 401
        assert client.post("/token", data=initial).status_code == 400
        assert client.get("/runs", headers=authentication(replacement)).status_code == 200


def test_terminal_uploads_discard_raw_log(tmp_path, monkeypatch):
    from mongo_store import create_upload_job, get_upload_job, set_upload_job_status

    monkeypatch.setenv("DEBUGIQ_STORAGE", "sqlite")
    monkeypatch.setenv("DEBUGIQ_SQLITE_PATH", str(tmp_path / "company.db"))
    for status in ("completed", "failed"):
        job = create_upload_job("private.log", "confidential sample")
        set_upload_job_status(job["_id"], "queued", error="previous error")
        assert get_upload_job(job["_id"])["raw_logs_text"] == "confidential sample"
        set_upload_job_status(job["_id"], status)
        result = get_upload_job(job["_id"])
        assert result["raw_logs_text"] is None
        assert result["error"] is None
