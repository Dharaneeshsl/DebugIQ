"""Live acceptance checks against an isolated production installation."""
import argparse
import httpx
from dotenv import dotenv_values


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    configuration = dotenv_values(args.env)
    with httpx.Client(base_url=args.url, timeout=60, trust_env=False) as client:
        assert client.get("/api/ready").status_code == 200
        assert client.get("/dashboard").status_code == 200
        assert client.get("/docs").status_code == 404
        assert client.get("/api/runs").status_code == 401
        assert client.post("/api/signup", json={"username": "blocked", "password": "12345678"}).status_code == 403
        token = client.post("/api/token", data={"username": configuration["DEBUGIQ_ADMIN_USERNAME"], "password": configuration["DEBUGIQ_ADMIN_PASSWORD"]})
        token.raise_for_status()
        client.headers["Authorization"] = "Bearer " + token.json()["access_token"]
        log = "[12:00:00.100] ERROR CPU line 10 UVM_ERROR: fetch timeout\n"
        upload = client.post("/api/upload", files={"file": ("release-check.log", log)})
        upload.raise_for_status()
        run_id = upload.json()["run_id"]
        try:
            dashboard = client.get(f"/api/dashboard/{run_id}")
            dashboard.raise_for_status()
            assert dashboard.json()["total_failures"] == 1
            assert client.get(f"/api/report/{run_id}").status_code == 200
        finally:
            client.delete(f"/api/run/{run_id}").raise_for_status()
        client.post("/api/logout").raise_for_status()
        assert client.get("/api/runs").status_code == 401
    print("Production acceptance passed: built UI, readiness, restricted registration/docs, authentication, upload, dashboard, CSV, cleanup and token revocation")
