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
