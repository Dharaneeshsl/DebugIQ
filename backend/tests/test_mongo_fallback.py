import importlib
import sys


def test_init_mongo_uses_fallback_store_when_mongo_is_unavailable(monkeypatch):
    monkeypatch.delenv("MONGO_URI", raising=False)
    monkeypatch.delenv("MONGODB_URI", raising=False)
    monkeypatch.setenv("MONGO_DB_NAME", "debugiq_test")

    sys.modules.pop("mongo_store", None)
    mongo_store = importlib.import_module("mongo_store")
    mongo_store._client = None

    mongo_store.init_mongo()
    user = mongo_store.create_user("demo", "hashed-password", "admin")

    assert user["username"] == "demo"
    assert mongo_store.get_user_by_username("demo")["username"] == "demo"
