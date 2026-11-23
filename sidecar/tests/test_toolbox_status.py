"""Toolbox map: per-server rows from ToolBox /status (shape from Tony's Mac, 2026-11-23)."""
from sidecar import toolbox_client


SAMPLE = {
    "uptime_seconds": 698351,
    "calls": 110,
    "servers": {
        "git": {"tools": 14, "state": "cold", "last_error": None, "starts": 9},
        "osa-system": {"tools": 32, "state": "running", "last_error": None},
        "mail": {"tools": 0, "state": "not running", "last_error": "connection refused"},
    },
}


def test_server_rows_pass_toolbox_labels_through_sorted():
    rows = toolbox_client.server_rows(SAMPLE["servers"])
    assert [r["name"] for r in rows] == ["git", "mail", "osa-system"]
    git = rows[0]
    assert git == {"name": "git", "state": "cold", "tools": 14, "error": None}


def test_error_comes_from_last_error():
    rows = {r["name"]: r for r in toolbox_client.server_rows(SAMPLE["servers"])}
    assert rows["mail"]["error"] == "connection refused"
    assert rows["osa-system"]["error"] is None


def test_status_includes_rows_and_totals(monkeypatch):
    monkeypatch.setattr(toolbox_client, "fetch_status", lambda url, timeout=2.0: SAMPLE)
    st = toolbox_client.status({"enabled": True, "url": "http://127.0.0.1:8795"})
    assert st["state"] == "connected"
    assert st["servers"] == 3
    assert st["tools"] == 46
    assert len(st["server_rows"]) == 3


def test_missing_or_odd_fields_do_not_break_rows():
    rows = toolbox_client.server_rows({"x": {}, "y": "not a dict"})
    assert rows == [
        {"name": "x", "state": "unknown", "tools": 0, "error": None},
        {"name": "y", "state": "unknown", "tools": 0, "error": None},
    ]
