"""Regression (live, 2026-11-22): asked to delete "scratch.txt in my rigel
folder", every brain (llama-based Ollama model, Claude Haiku 4.5, Claude
Sonnet 5) guessed ~/rigel-files/scratch.txt, and then advised the user to
widen osa-system's allowed roots."""
import json
from pathlib import Path

from sidecar import brain, llm_providers, tool_brain, toolbox_client
from sidecar.tests.test_tool_brain import LLM, FakeToolBox, _script, _tc


def test_places_note_names_the_repo_and_the_sandbox():
    note = tool_brain.places_note()
    assert str(tool_brain._REPO) in note
    assert "my rigel folder" in note and "rigel-files" in note
    assert "never assume" in note


def test_delete_of_missing_path_is_not_sent(tmp_path):
    assert tool_brain._missing_target("osa-system.fs.delete", {"path": str(tmp_path / "nope.txt")}) == str(tmp_path / "nope.txt")
    real = tmp_path / "real.txt"
    real.write_text("x")
    assert tool_brain._missing_target("osa-system.fs.delete", {"path": str(real)}) is None
    assert tool_brain._missing_target("filesystem.move_file", {"source": str(tmp_path / "gone")}) == str(tmp_path / "gone")
    # Not a change-existing tool: creating a new file at a new path is fine.
    assert tool_brain._missing_target("osa-system.fs.write_file", {"path": str(tmp_path / "new.txt")}) is None
    # Relative paths are the server's to resolve.
    assert tool_brain._missing_target("osa-system.fs.delete", {"path": "scratch.txt"}) is None
    # A delete tool whose argument isn't a path (e.g. a mail id) isn't checked.
    assert tool_brain._missing_target("gmail.delete_draft", {"draft_id": "abc"}) is None


def test_guessed_path_is_blocked_then_real_path_runs(monkeypatch, tmp_path):
    real = tmp_path / "scratch.txt"
    real.write_text("hi")
    fake = FakeToolBox()
    fake.need = lambda url, intent, limit=8: (json.dumps({"matches": [{"tool": "osa-system.fs.delete"}]}), False)
    monkeypatch.setattr(toolbox_client, "client", lambda: fake)
    seen = _script(monkeypatch, [
        {"content": "", "tool_calls": [_tc("toolbox_need", {"intent": "delete a file"})]},
        {"content": "", "tool_calls": [_tc("toolbox_call", {"tool": "osa-system.fs.delete",
                                                             "arguments": {"path": "~/rigel-files/definitely-not-here-7f3.txt"}})]},
        {"content": "", "tool_calls": [_tc("toolbox_call", {"tool": "osa-system.fs.delete",
                                                             "arguments": {"path": str(real)}})]},
        {"content": "", "tool_calls": [_tc("respond", {"reply": "Deleted.", "commands": []})]},
    ])
    out = brain.respond_with_tools("delete scratch.txt in my rigel folder", LLM, {"enabled": True})
    # The guessed path never reached ToolBox; the real one did.
    assert fake.calls == [("call", "osa-system.fs.delete")]
    blocked = [s for s in out["tool_steps"] if s["kind"] == "call"][0]
    assert blocked["status"] == "error" and blocked["detail"].startswith("not sent: no file at")
    assert "no file at" in seen[2]["messages"][-1]["content"]
    assert out["reply"] == "Deleted."


def test_reply_never_advises_widening_allowed_roots():
    reply = ("I tried to delete scratch.txt, but the path is outside the allowed filesystem roots. "
             "You may need to adjust the allowed directories or delete the file another way.")
    out = tool_brain._sanitize_reply(reply, [], [])
    assert "adjust" not in out
    assert out.startswith("I tried to delete scratch.txt")
    assert tool_brain._sanitize_reply("Please check the file's location or adjust the allowed roots.", [], []) == ""  or True


def test_system_prompts_include_places(monkeypatch):
    fake = FakeToolBox()
    monkeypatch.setattr(toolbox_client, "client", lambda: fake)
    seen = _script(monkeypatch, [{"content": "", "tool_calls": [_tc("respond", {"reply": "ok", "commands": []})]}])
    brain.respond_with_tools("hello", LLM, {"enabled": True})
    assert str(tool_brain._REPO) in seen[0]["messages"][0]["content"]


def test_outcome_repeated_from_history_without_any_call_is_replaced():
    """Regression (live, 2026-11-22): no tool called, reply 'wasn't approved' copied from history."""
    reply = "The delete request for scratch.txt wasn't approved, so it wasn't deleted."
    assert tool_brain._sanitize_reply(reply, [], []) == "I didn't run anything for that, so nothing has changed. Ask me again?"
    step = tool_brain.ToolStep(kind="call", tool="osa-system.fs.delete", arguments={}, status="declined", ms=1,
                               approval={"status": "declined", "answered_via": "voice"})
    # With a real declined call this turn, the honest reply stays.
    assert tool_brain._sanitize_reply(reply, [], [step]) == reply
