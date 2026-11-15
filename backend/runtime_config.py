"""Fail closed when running an installation intended for company use."""
import os


def production():
    return os.getenv("DEBUGIQ_ENV", "development").lower() == "production"


def external_ai_allowed():
    return os.getenv("DEBUGIQ_ALLOW_EXTERNAL_AI", "false").lower() == "true"


def validate_production():
    if not production():
        return
    secret = os.getenv("DEBUGIQ_JWT_SECRET", "")
    password = os.getenv("DEBUGIQ_ADMIN_PASSWORD", "")
    if len(secret) < 48 or "replace" in secret.lower():
        raise RuntimeError("Production requires DEBUGIQ_JWT_SECRET with at least 48 random characters")
    if len(password) < 16 or password.lower() == "admin123":
        raise RuntimeError("Production requires a strong DEBUGIQ_ADMIN_PASSWORD of at least 16 characters")
    if os.getenv("DEBUGIQ_STORAGE", "sqlite") != "sqlite" and not (os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")):
        raise RuntimeError("MongoDB production storage requires a MongoDB URI")
    if os.getenv("DEBUGIQ_RATE_LIMIT_STORAGE", "memory://") == "":
        raise RuntimeError("Rate-limit storage cannot be empty")
