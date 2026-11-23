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

        -- Every ToolBox step the brain takes (need / call), tied to the
        -- Rigel reply turn it served. Additive table: existing DBs gain it
        -- on next launch, nothing else changes. arguments is a JSON blob;
        -- full tool output is never stored (can hold mail, file contents).
        CREATE TABLE IF NOT EXISTS tool_calls (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ts        TEXT    NOT NULL,
            turn_id   INTEGER,                  -- the rigel reply turn
            kind      TEXT    NOT NULL,         -- 'need' | 'call'
            tool      TEXT    NOT NULL,         -- server.tool, or the need() query
            arguments TEXT    NOT NULL,         -- JSON blob
            status    TEXT    NOT NULL,         -- 'ok' | 'error' | 'declined' | 'expired'
            ms        INTEGER NOT NULL,
            detail    TEXT,
            approval  TEXT,                     -- JSON {status, answered_via} or NULL
            FOREIGN KEY (turn_id) REFERENCES turns (id)
        );

        CREATE INDEX IF NOT EXISTS idx_tool_calls_turn ON tool_calls(turn_id);
        """
    )
    conn.commit()
    _migrate_conversations(conn)
    _migrate_voice_profiles(conn)


def _migrate_conversations(conn: sqlite3.Connection) -> None:
    """Add the conversations table and turns.conversation_id (idempotent).

    Existing turns are assigned to one default conversation so history is
    kept. A DB backup is written before the first ALTER.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT    NOT NULL,
            title      TEXT
        );
        """
    )
    cols = {row[1] for row in conn.execute("PRAGMA table_info(turns)")}
    if "conversation_id" not in cols:
        has_turns = conn.execute("SELECT 1 FROM turns LIMIT 1").fetchone() is not None
        if has_turns:
            _backup_before_migration(conn)  # only existing data needs protecting
        conn.execute(
            "ALTER TABLE turns ADD COLUMN conversation_id INTEGER "
            "REFERENCES conversations (id)"
        )
        if has_turns:
            cur = conn.execute(
                "INSERT INTO conversations (started_at, title) VALUES (?, ?)",
                (_now(), "Earlier conversation"),
            )
            conn.execute(
                "UPDATE turns SET conversation_id = ? WHERE conversation_id IS NULL",
                (cur.lastrowid,),
            )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_turns_conversation ON turns(conversation_id)"
    )
    conn.commit()


def _backup_before_migration(conn: sqlite3.Connection) -> None:
    """Copy the DB file aside before a schema change. In-memory DBs have no file."""
    row = conn.execute("PRAGMA database_list").fetchone()
    file_path = row[2] if row else ""
    if not file_path:
        return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    backup = Path(f"{file_path}.pre-conversations-{stamp}.bak")
    if not backup.exists():
        conn.execute("PRAGMA wal_checkpoint(FULL)")  # fold WAL into the main file first
        backup.write_bytes(Path(file_path).read_bytes())


def _migrate_voice_profiles(conn: sqlite3.Connection) -> None:
    """Add the voice_profiles table (idempotent). New table only: no existing
    rows are touched, so no backup is needed. One row per enrolled model."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS voice_profiles (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at   TEXT    NOT NULL,
            model        TEXT    NOT NULL,
            embeddings   TEXT    NOT NULL,   -- JSON: list of enrollment vectors
            UNIQUE (model)
        );
        """
    )
    conn.commit()


def save_voice_profile(model: str, embeddings: list[list[float]]) -> None:
    """Store the enrollment vectors for one model, replacing any earlier profile."""
    if not embeddings or not all(embeddings):
        raise ValueError("a voice profile needs at least one non-empty embedding")
    conn = connect()
    conn.execute(
        "INSERT INTO voice_profiles (created_at, model, embeddings) VALUES (?, ?, ?) "
        "ON CONFLICT(model) DO UPDATE SET created_at = excluded.created_at, "
        "embeddings = excluded.embeddings",
        (_now(), model, json.dumps(embeddings)),
    )
    conn.commit()


def get_voice_profile(model: str) -> dict | None:
    """The stored profile for one model, or None if the user hasn't enrolled."""
    row = connect().execute(
        "SELECT created_at, model, embeddings FROM voice_profiles WHERE model = ?", (model,)
    ).fetchone()
    if row is None:
        return None
    return {"created_at": row[0], "model": row[1], "embeddings": json.loads(row[2])}


def delete_voice_profile(model: str) -> bool:
    conn = connect()
    cur = conn.execute("DELETE FROM voice_profiles WHERE model = ?", (model,))
    conn.commit()
    return cur.rowcount > 0


# ── conversations ──────────────────────────────────────────────────────────

def _active_conversation_id(conn: sqlite3.Connection) -> int:
    """Id of the newest conversation; creates one if none exists. Caller holds _LOCK."""
    row = conn.execute("SELECT MAX(id) FROM conversations").fetchone()
    if row and row[0] is not None:
        return int(row[0])
    cur = conn.execute(
        "INSERT INTO conversations (started_at, title) VALUES (?, ?)", (_now(), None)
    )
    conn.commit()
    return int(cur.lastrowid)


def active_conversation_id() -> int:
    conn = connect()
    with _LOCK:
        return _active_conversation_id(conn)


def start_new_conversation(title: str | None = None) -> int:
    """Start a fresh conversation. Older turns stay in the DB, untouched."""
    conn = connect()
    with _LOCK:
        cur = conn.execute(
            "INSERT INTO conversations (started_at, title) VALUES (?, ?)", (_now(), title)
        )
        conn.commit()
        return int(cur.lastrowid)


def list_conversations(limit: int = 100) -> list[dict]:
    conn = connect()
    rows = conn.execute(
        "SELECT c.id, c.started_at, c.title, COUNT(t.id) AS turn_count "
        "FROM conversations c LEFT JOIN turns t ON t.conversation_id = c.id "
        "GROUP BY c.id ORDER BY c.id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def conversation_history(conversation_id: int, before_turn_id: int, limit: int = 20) -> list[dict]:
    """Earlier turns of one conversation as chat messages for the model.

    Rigel's replies become 'assistant'. Consecutive same-role turns are merged
    and a leading assistant turn is dropped, so roles alternate and start with
    'user' (what the Claude API expects). The current turn is excluded.
    """
    conn = connect()
    rows = conn.execute(
        "SELECT role, text FROM turns WHERE conversation_id = ? AND id < ? "
        "ORDER BY id DESC LIMIT ?",
        (conversation_id, before_turn_id, limit),
    ).fetchall()
    msgs: list[dict] = []
    for r in reversed(rows):
        role = "user" if r["role"] == "user" else "assistant"
        if msgs and msgs[-1]["role"] == role:
            msgs[-1]["content"] += "\n" + r["text"]
        else:
            msgs.append({"role": role, "content": r["text"]})
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    return msgs


def conversation_turns(conversation_id: int) -> list[dict]:
    conn = connect()
    rows = conn.execute(
        "SELECT id, ts, role, text FROM turns WHERE conversation_id = ? ORDER BY id",
        (conversation_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── writes ─────────────────────────────────────────────────────────────────

def log_turn(role: str, text: str) -> int:
    conn = connect()
    with _LOCK:
        conv_id = _active_conversation_id(conn)
        cur = conn.execute(
            "INSERT INTO turns (ts, role, text, conversation_id) VALUES (?, ?, ?, ?)",
            (_now(), role, text, conv_id),
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


def log_tool_steps(turn_id: int, steps: list[dict]) -> None:
    if not steps:
        return
    conn = connect()
    now = _now()
    with _LOCK:
        conn.executemany(
            "INSERT INTO tool_calls (ts, turn_id, kind, tool, arguments, status, ms, detail, approval) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (now, turn_id, st["kind"], st["tool"], json.dumps(st.get("arguments") or {}),
                 st["status"], int(st.get("ms") or 0), st.get("detail") or "",
                 json.dumps(st["approval"]) if st.get("approval") else None)
                for st in steps
            ],
        )
        conn.commit()


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


def tool_steps_for_turns(turn_ids: list[int]) -> dict[int, list[dict]]:
    """ToolBox steps grouped by the reply turn they served (for rehydration)."""
    if not turn_ids:
        return {}
    conn = connect()
    marks = ",".join("?" * len(turn_ids))
    rows = conn.execute(
        f"SELECT turn_id, kind, tool, arguments, status, ms, detail, approval "
        f"FROM tool_calls WHERE turn_id IN ({marks}) ORDER BY id", turn_ids
    ).fetchall()
    out: dict[int, list[dict]] = {}
    for r in rows:
        d = dict(r)
        d["arguments"] = json.loads(d["arguments"]) if d["arguments"] else {}
        d["approval"] = json.loads(d["approval"]) if d["approval"] else None
        out.setdefault(d.pop("turn_id"), []).append(d)
    return out
