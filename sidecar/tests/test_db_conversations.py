"""Conversations migration and New Chat behaviour in sidecar/db.py.

Each test points db at a fresh temp file via RIGEL_DB and resets the cached
connection, so the real ~/.rigel/rigel.db is never touched.
"""
import importlib
import sqlite3

import pytest


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("RIGEL_DB", str(tmp_path / "rigel.db"))
    import sidecar.db as db
    db = importlib.reload(db)
    db._CONN = None
    yield db
    if db._CONN is not None:
        db._CONN.close()
        db._CONN = None


def test_fresh_db_turns_land_in_one_conversation(fresh_db):
    db = fresh_db
    db.log_turn("user", "hello")
    db.log_turn("rigel", "hi")
    turns = db.conversation_turns(db.active_conversation_id())
    assert [t["text"] for t in turns] == ["hello", "hi"]
    assert len(db.list_conversations()) == 1


def test_new_chat_keeps_old_transcript_and_starts_empty(fresh_db):
    db = fresh_db
    db.log_turn("user", "old question")
    old_id = db.active_conversation_id()
    new_id = db.start_new_conversation()
    assert new_id != old_id
    assert db.active_conversation_id() == new_id
    assert db.conversation_turns(new_id) == []
    db.log_turn("user", "new question")
    assert [t["text"] for t in db.conversation_turns(old_id)] == ["old question"]
    assert [t["text"] for t in db.conversation_turns(new_id)] == ["new question"]
    counts = {c["id"]: c["turn_count"] for c in db.list_conversations()}
    assert counts == {old_id: 1, new_id: 1}


def test_legacy_db_is_backfilled_into_one_conversation_with_backup(tmp_path, monkeypatch):
    path = tmp_path / "rigel.db"
    # Build a pre-change database: turns without conversation_id.
    raw = sqlite3.connect(str(path))
    raw.executescript(
        "CREATE TABLE turns (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL,"
        " role TEXT NOT NULL, text TEXT NOT NULL);"
        "INSERT INTO turns (ts, role, text) VALUES ('t1','user','a'),('t2','rigel','b');"
    )
    raw.commit(); raw.close()

    monkeypatch.setenv("RIGEL_DB", str(path))
    import sidecar.db as db
    db = importlib.reload(db)
    db._CONN = None
    try:
        convs = db.list_conversations()
        assert len(convs) == 1 and convs[0]["turn_count"] == 2
        assert [t["text"] for t in db.conversation_turns(convs[0]["id"])] == ["a", "b"]
        backups = list(tmp_path.glob("rigel.db.pre-conversations-*.bak"))
        assert len(backups) == 1
    finally:
        db._CONN.close(); db._CONN = None


def test_migration_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("RIGEL_DB", str(tmp_path / "rigel.db"))
    import sidecar.db as db
    db = importlib.reload(db)
    db._CONN = None
    db.log_turn("user", "x")
    db._CONN.close(); db._CONN = None
    db.log_turn("user", "y")  # reconnects and re-runs _migrate
    assert [t["text"] for t in db.conversation_turns(db.active_conversation_id())] == ["x", "y"]
    assert list(tmp_path.glob("rigel.db.pre-conversations-*.bak")) == []  # no second backup
    db._CONN.close(); db._CONN = None


def test_history_is_alternating_excludes_current_and_drops_leading_reply(fresh_db):
    db = fresh_db
    db.log_turn("rigel", "stray opener")        # leading assistant turn: dropped
    db.log_turn("user", "My sister is Priya.")
    db.log_turn("user", "Remember that.")       # two user turns in a row: merged
    db.log_turn("rigel", "Got it.")
    current = db.log_turn("user", "Who is my sister?")
    history = db.conversation_history(db.active_conversation_id(), current)
    assert history == [
        {"role": "user", "content": "My sister is Priya.\nRemember that."},
        {"role": "assistant", "content": "Got it."},
    ]


def test_history_is_empty_in_a_new_chat(fresh_db):
    db = fresh_db
    db.log_turn("user", "old")
    db.log_turn("rigel", "old reply")
    db.start_new_conversation()
    current = db.log_turn("user", "fresh question")
    assert db.conversation_history(db.active_conversation_id(), current) == []
