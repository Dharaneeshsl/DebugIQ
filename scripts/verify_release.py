"""Extract and run the distribution in a fresh directory using the installed release dependencies."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import socket
import subprocess
import sys
import tempfile
import time
from zipfile import ZipFile

from dotenv import dotenv_values
import httpx


def extract_verified(archive, destination):
    expected = archive.with_suffix(".zip.sha256").read_text(encoding="utf-8-sig").strip().lower()
    with archive.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
            raise ValueError("Release checksum mismatch")
    with ZipFile(archive) as package:
        entries = {entry.filename.replace("\\", "/"): entry for entry in package.infolist() if not entry.is_dir()}
        manifest = json.loads(package.read(entries.pop("manifest.json")).decode("utf-8-sig"))
        if set(entries) != {item["path"].replace("\\", "/") for item in manifest}:
            raise ValueError("Release contents differ from the manifest")
        for item in manifest:
            name = item["path"].replace("\\", "/")
            filename = PurePosixPath(name)
            if filename.is_absolute() or ".." in filename.parts or ":" in name:
                raise ValueError(f"Invalid archive path: {name}")
            content = package.read(entries[name])
            if hashlib.sha256(content).hexdigest() != item["sha256"].lower():
                raise ValueError(f"File checksum mismatch: {name}")
            target = destination.joinpath(*filename.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)


@contextmanager
def serve(root, env, configuration):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--app-dir", "backend", "--env-file", str(configuration),
             "--host", "127.0.0.1", "--port", str(port), "--no-proxy-headers", "--no-access-log"],
            cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 30
            with httpx.Client(base_url=url, trust_env=False, timeout=1) as client:
                while time.monotonic() < deadline and process.poll() is None:
                    try:
                        if client.get("/ready").status_code == 200:
                            break
                    except httpx.RequestError:
                        pass
                    time.sleep(0.25)
                else:
                    log.seek(0)
                    raise RuntimeError(log.read().decode(errors="replace"))
            yield url
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    archive = parser.parse_args().archive.resolve()
    excluded = ("DEBUGIQ_", "MONGO", "RABBITMQ", "CORS_ALLOWED_ORIGINS", "PYTHONPATH")
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith(excluded)}
    env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")

    with tempfile.TemporaryDirectory(prefix="debugiq-acceptance-", dir=archive.parent) as temp:
        root = Path(temp)
        extract_verified(archive, root)

        def run(*args):
            subprocess.run([sys.executable, *args], cwd=root, env=env, check=True)

        run("backend/provision_production.py")
        configuration = root / "backend/.env.production"
        options = dotenv_values(configuration)
        database = Path(options["DEBUGIQ_SQLITE_PATH"])
        backup = database.with_name("acceptance-backup.sqlite3")
        with serve(root, env, configuration) as url:
            run("backend/release_check.py", "--env", str(configuration), "--url", url)
            run("backend/backup_store.py", str(database), str(backup))

        restored = database.with_name("acceptance-restore.sqlite3")
        run("backend/backup_store.py", str(backup), str(restored))
        env["DEBUGIQ_SQLITE_PATH"] = str(restored)
        with serve(root, env, configuration) as url:
            run("backend/release_check.py", "--env", str(configuration), "--url", url)
    print("Verified the archive and completed production acceptance before and after database restore.")


if __name__ == "__main__":
    main()
