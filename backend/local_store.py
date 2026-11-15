"""Persistent, embedded document storage for a single-machine installation.

Implements the small collection interface used by mongo_store; MongoDB remains
available for shared deployments. Each write transaction is serialized by SQLite.
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from pymongo.errors import DuplicateKeyError


def _encode(value):
    if isinstance(value, datetime):
        return {"__debugiq_datetime__": value.isoformat()}
    raise TypeError(type(value).__name__)


def _decode(value):
    if set(value) == {"__debugiq_datetime__"}:
        return datetime.fromisoformat(value["__debugiq_datetime__"])
    return value


def _matches(doc, query):
    return all(
        doc.get(key) in value["$in"] if isinstance(value, dict) and "$in" in value
        else doc.get(key) == value
        for key, value in query.items()
    )


class Cursor(list):
    def sort(self, key, direction=1):
        return Cursor(sorted(self, key=lambda row: row.get(key), reverse=direction == -1))

    def skip(self, count):
        return Cursor(self[count:])

    def limit(self, count):
        return Cursor(self[:count])


class LocalCollection:
    def __init__(self, name):
        self.name = name

    @contextmanager
    def _connect(self):
        path = Path(os.environ.get("DEBUGIQ_SQLITE_PATH", Path(__file__).parent / "data" / "debugiq.sqlite3"))
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=30)
        connection.execute("CREATE TABLE IF NOT EXISTS documents (collection TEXT, id TEXT, body TEXT NOT NULL, PRIMARY KEY(collection, id))")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create_index(self, *args, **kwargs):
        # _id is indexed by the primary key; username uniqueness is enforced in
        # the same immediate transaction as user insertion.
        return None

    def _rows(self, connection):
        return [json.loads(row[0], object_hook=_decode) for row in connection.execute(
            "SELECT body FROM documents WHERE collection=? ORDER BY rowid", (self.name,))]

    def find(self, query=None, projection=None):
        with self._connect() as connection:
            rows = [row for row in self._rows(connection) if _matches(row, query or {})]
        if projection:
            keys = {key for key, included in projection.items() if included} | {"_id"}
            rows = [{key: value for key, value in row.items() if key in keys} for row in rows]
        return Cursor(rows)

    def find_one(self, query, sort=None):
        rows = self.find(query)
        for key, direction in reversed(sort or []):
            rows = rows.sort(key, direction)
        return rows[0] if rows else None

    def _save(self, connection, doc, *, insert=False):
        operation = "INSERT" if insert else "INSERT OR REPLACE"
        connection.execute(f"{operation} INTO documents VALUES (?, ?, ?)",
                           (self.name, json.dumps(doc["_id"]), json.dumps(doc, default=_encode)))

    def insert_one(self, doc):
        self.insert_many([doc])

    def insert_many(self, docs):
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                for doc in docs:
                    if self.name == "users" and any(row["username"] == doc["username"] for row in self._rows(connection)):
                        raise DuplicateKeyError("Username already exists")
                    self._save(connection, doc, insert=True)
            except sqlite3.IntegrityError as exc:
                raise DuplicateKeyError("Document already exists") from exc

    def find_one_and_update(self, query, update, upsert=False, return_document=None):
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            doc = next((row for row in self._rows(connection) if _matches(row, query)), None)
            if doc is None:
                if not upsert:
                    return None
                doc = dict(query)
            doc.update(update.get("$set", {}))
            for key, value in update.get("$inc", {}).items():
                doc[key] = doc.get(key, 0) + value
            self._save(connection, doc)
            return doc

    def update_one(self, query, update, upsert=False):
        return self.find_one_and_update(query, update, upsert=upsert)

    def delete_many(self, query):
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = [row for row in self._rows(connection) if _matches(row, query)]
            connection.executemany("DELETE FROM documents WHERE collection=? AND id=?",
                                   [(self.name, json.dumps(row["_id"])) for row in rows])
        return SimpleNamespace(deleted_count=len(rows))

    def delete_one(self, query):
        row = self.find_one(query)
        return self.delete_many({"_id": row["_id"]}) if row else SimpleNamespace(deleted_count=0)


class LocalDatabase:
    def __getitem__(self, name):
        return LocalCollection(name)
