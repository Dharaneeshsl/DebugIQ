"""SQLite online backup and non-overwriting offline restore for local installations."""
import argparse
import sqlite3
from pathlib import Path


def backup(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file() or destination.exists() or source == destination:
        raise ValueError("Source must exist and backup destination must be new")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as reader:
        with sqlite3.connect(destination) as writer:
            reader.backup(writer)
            if writer.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Backup integrity check failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Back up live SQLite or restore to a NEW path with the API stopped")
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    backup(args.source, args.destination)
    print("Copy completed and SQLite integrity verified")
