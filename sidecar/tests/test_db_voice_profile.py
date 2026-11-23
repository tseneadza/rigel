"""Voice profile storage in sidecar/db.py. Each test uses a fresh temp DB via
RIGEL_DB, so the real ~/.rigel/rigel.db is never touched."""
import importlib

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


def test_no_profile_until_enrolled(fresh_db):
    assert fresh_db.get_voice_profile("ecapa") is None


def test_save_then_read_round_trips(fresh_db):
    vecs = [[0.1, 0.2, 0.3], [0.1, 0.25, 0.28], [0.12, 0.2, 0.31]]
    fresh_db.save_voice_profile("ecapa", vecs)
    got = fresh_db.get_voice_profile("ecapa")
    assert got["model"] == "ecapa" and got["embeddings"] == vecs and got["created_at"]


def test_resave_replaces_the_profile(fresh_db):
    fresh_db.save_voice_profile("ecapa", [[1.0, 0.0]])
    fresh_db.save_voice_profile("ecapa", [[0.0, 1.0], [0.5, 0.5]])
    got = fresh_db.get_voice_profile("ecapa")
    assert got["embeddings"] == [[0.0, 1.0], [0.5, 0.5]]


def test_profiles_are_per_model(fresh_db):
    fresh_db.save_voice_profile("ecapa", [[1.0]])
    fresh_db.save_voice_profile("wespeaker", [[2.0]])
    assert fresh_db.get_voice_profile("ecapa")["embeddings"] == [[1.0]]
    assert fresh_db.get_voice_profile("wespeaker")["embeddings"] == [[2.0]]


def test_delete_removes_profile(fresh_db):
    fresh_db.save_voice_profile("ecapa", [[1.0]])
    assert fresh_db.delete_voice_profile("ecapa") is True
    assert fresh_db.get_voice_profile("ecapa") is None
    assert fresh_db.delete_voice_profile("ecapa") is False


@pytest.mark.parametrize("bad", [[], [[]]])
def test_empty_profile_is_rejected(fresh_db, bad):
    with pytest.raises(ValueError):
        fresh_db.save_voice_profile("ecapa", bad)


def test_migration_is_idempotent_and_keeps_turns(fresh_db):
    fresh_db.log_turn("user", "hello")
    fresh_db.connect().close()
    fresh_db._CONN = None
    fresh_db.connect()  # runs migrations again on the same file
    assert [t["text"] for t in fresh_db.recent_turns(10)] == ["hello"]
