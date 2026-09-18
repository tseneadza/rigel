"""Rigel's own log/memory store — SQLite, stdlib only.

Two tables from day one, per the project's founding requirement:

  * ``turns``            — every conversation turn (user + rigel), in order.
  * ``command_attempts`` — every command Rigel *tries* to implement, whether
                           it ran, was deferred, or was blocked.

The DB lives at ``~/.rigel/rigel.db`` (user-scoped, never in the repo). The
path is overridable with ``$RIGEL_DB`` so tests can point at a temp file.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.Lock()
_CONN: sqlite3.Connection | None = None


def _db_path() -> Path:
    override = os.getenv("RIGEL_DB")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".rigel" / "rigel.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    """Return the process-wide connection, creating + migrating on first use."""
    global _CONN
    if _CONN is not None:
        return _CONN
    with _LOCK:
        if _CONN is not None:
            return _CONN
        path = _db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        _migrate(conn)
        _CONN = conn
        return conn


def _migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS turns (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ts       TEXT    NOT NULL,
            role     TEXT    NOT NULL,          -- 'user' | 'rigel'
            text     TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS command_attempts (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ts        TEXT    NOT NULL,
            turn_id   INTEGER,                  -- the user turn that triggered it
            action    TEXT    NOT NULL,         -- e.g. 'open_app', 'create_file'
            args      TEXT    NOT NULL,         -- JSON blob
            status    TEXT    NOT NULL,         -- 'pending' | 'ok' | 'blocked' | 'rejected' | 'error'
            detail    TEXT,                     -- human-readable note
            FOREIGN KEY (turn_id) REFERENCES turns (id)
        );

        CREATE TABLE IF NOT EXISTS settings (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            key          TEXT    UNIQUE NOT NULL,
            value        TEXT    NOT NULL,
            last_updated TEXT    NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(key);
        """
    )
    conn.commit()


# ── writes ─────────────────────────────────────────────────────────────────

def log_turn(role: str, text: str) -> int:
    conn = connect()
    with _LOCK:
        cur = conn.execute(
            "INSERT INTO turns (ts, role, text) VALUES (?, ?, ?)",
            (_now(), role, text),
        )
        conn.commit()
        return int(cur.lastrowid)


def log_command(action: str, args: dict, status: str, detail: str = "",
                turn_id: int | None = None) -> int:
    conn = connect()
    with _LOCK:
        cur = conn.execute(
            "INSERT INTO command_attempts (ts, turn_id, action, args, status, detail) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (_now(), turn_id, action, json.dumps(args), status, detail),
        )
        conn.commit()
        return int(cur.lastrowid)


# ── reads ──────────────────────────────────────────────────────────────────

def recent_turns(limit: int = 50) -> list[dict]:
    conn = connect()
    rows = conn.execute(
        "SELECT id, ts, role, text FROM turns ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_command(command_id: int) -> dict | None:
    conn = connect()
    row = conn.execute(
        "SELECT id, ts, turn_id, action, args, status, detail "
        "FROM command_attempts WHERE id = ?", (command_id,)
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["args"] = json.loads(d["args"]) if d["args"] else {}
    return d


def update_command_status(command_id: int, status: str, detail: str = "") -> None:
    conn = connect()
    with _LOCK:
        conn.execute(
            "UPDATE command_attempts SET status = ?, detail = ? WHERE id = ?",
            (status, detail, command_id),
        )
        conn.commit()


def recent_commands(limit: int = 50) -> list[dict]:
    conn = connect()
    rows = conn.execute(
        "SELECT id, ts, turn_id, action, args, status, detail "
        "FROM command_attempts ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["args"] = json.loads(d["args"]) if d["args"] else {}
        out.append(d)
    return list(reversed(out))


def get_setting(key: str) -> dict | None:
    """Fetch a setting by key. Returns parsed JSON or None if not found."""
    conn = connect()
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    ).fetchone()
    return json.loads(row[0]) if row else None


def set_setting(key: str, value: dict) -> str:
    """Save or update a setting. Returns last_updated timestamp."""
    conn = connect()
    now = _now()
    with _LOCK:
        conn.execute(
            "INSERT INTO settings (key, value, last_updated) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, last_updated=excluded.last_updated",
            (key, json.dumps(value), now)
        )
        conn.commit()
    return now
