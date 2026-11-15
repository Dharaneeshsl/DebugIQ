"""Generate an isolated company's installation configuration, without logging secrets."""
import secrets
from pathlib import Path


if __name__ == "__main__":
    destination = Path(__file__).parent / ".env.production"
    with destination.open("x", encoding="utf-8") as output:
        output.write("\n".join([
            "DEBUGIQ_ENV=production", "DEBUGIQ_STORAGE=sqlite",
            "DEBUGIQ_SQLITE_PATH=" + (Path(__file__).parent / "data/company.sqlite3").as_posix(),
            "DEBUGIQ_EMBEDDINGS_BACKEND=tfidf", "DEBUGIQ_ADMIN_USERNAME=company-admin",
            "DEBUGIQ_ADMIN_PASSWORD=" + secrets.token_urlsafe(24),
            "DEBUGIQ_JWT_SECRET=" + secrets.token_urlsafe(48),
            "DEBUGIQ_ALLOW_EXTERNAL_AI=false", "CORS_ALLOWED_ORIGINS=",
            "DEBUGIQ_MAX_UPLOAD_BYTES=10485760", "DEBUGIQ_MAX_FAILURES=3000", "",
        ]))
    print("Created backend/.env.production. Restrict its file permissions and retrieve the generated initial credentials privately.")
