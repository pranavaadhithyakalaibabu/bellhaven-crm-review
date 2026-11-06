"""Remember review decisions, snapshots and write attempts between runs."""

import os
import sqlite3
import contextlib
import fcntl
import settings
from common import digest, now, encode


@contextlib.contextmanager
def lock():
    with open(settings.DATA / "pipeline.lock", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def db():
    """Open the local decision ledger for this CRM token and base URL."""
    connection = sqlite3.connect(settings.DATA / "review.sqlite", timeout=60)
    connection.row_factory = sqlite3.Row
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS proposals (
            id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'pending',
            reviewer TEXT,
            reason TEXT,
            decided_at TEXT,
            result TEXT,
            phase TEXT,
            error TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            summary TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY,
            at TEXT NOT NULL,
            proposal_id TEXT,
            event TEXT,
            detail TEXT
        );
        CREATE TABLE IF NOT EXISTS confirmations (
            proposal_id TEXT PRIMARY KEY REFERENCES proposals(id),
            reviewer TEXT NOT NULL,
            reason TEXT NOT NULL,
            confirmed_at TEXT NOT NULL
        );
        """)
    token = os.environ.get("CRM_TOKEN")
    if token:
        scope = digest({"base": settings.BASE, "token": token})
        saved = connection.execute(
            "SELECT value FROM metadata WHERE key='scope'"
        ).fetchone()
        if saved and saved[0] != scope:
            raise RuntimeError(
                "This decision database belongs to a different CRM token/base. Use a separate BELLHAVEN_DATA directory."
            )
        connection.execute("INSERT OR IGNORE INTO metadata VALUES('scope',?)", (scope,))
        connection.commit()
    return connection


def audit(connection, proposal_id, event, detail):
    connection.execute(
        "INSERT INTO audit(at,proposal_id,event,detail) VALUES(?,?,?,?)",
        (now(), proposal_id, event, encode(detail)),
    )
    connection.commit()
