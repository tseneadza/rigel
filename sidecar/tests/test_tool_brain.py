"""Tool-loop tests with a fake ToolBox and a scripted Ollama."""
import json

import pytest

from sidecar import brain, llm_providers, tool_brain, toolbox_client


class FakeToolBox:
    def __init__(self, up=True):
        self.up = up
        self.calls = []

    def ping(self, url):
        if not self.up:
            raise toolbox_client.ToolBoxUnavailable("ToolBox unreachable at test")

    def need(self, url, intent, limit=8):
        self.calls.append(("need", intent))
        return json.dumps({"matches": [{"tool": "osa-system.health.battery", "input_schema": {}}]}), False

    def call(self, url, tool, arguments):
        self.calls.append(("call", tool))
        return json.dumps({"summary": "100%, health 85%"}), False, []


def _script(monkeypatch, replies):
    seen = []

    def fake(host, path, body, timeout):
        if path == "/api/show":
            return {"capabilities": ["completion", "tools"]}
        seen.append(json.loads(json.dumps(body)))  # snapshot: the loop keeps appending to messages
        return {"message": replies.pop(0)}
    monkeypatch.setattr(llm_providers, "_ollama_request", fake)
    return seen


def _tc(name, args):
    return {"function": {"name": name, "arguments": args}}


LLM = {"provider": "ollama", "ollama_model": "llama3.2:3b", "ollama_host": "http://x"}


def test_need_call_respond(monkeypatch):
    fake = FakeToolBox()
    monkeypatch.setattr(toolbox_client, "client", lambda: fake)
    seen = _script(monkeypatch, [
        {"content": "", "tool_calls": [_tc("toolbox_need", {"intent": "battery"})]},
        {"content": "", "tool_calls": [_tc("toolbox_call", {"tool": "osa-system.health.battery", "arguments": {}})]},
        {"content": "", "tool_calls": [_tc("respond", {"reply": "Battery is full.", "commands": []})]},
    ])
    out = brain.respond_with_tools("how's my battery?", LLM, {"enabled": True})
    assert out["reply"] == "Battery is full."
    assert out["toolbox"]["state"] == "used"
    assert [s["kind"] for s in out["tool_steps"]] == ["need", "call"]
    assert out["tool_steps"][1]["tool"] == "osa-system.health.battery"
    # tool results were fed back to the model
    assert seen[-1]["messages"][-1]["role"] == "tool"


def test_max_steps_forces_respond(monkeypatch):
    fake = FakeToolBox()
    monkeypatch.setattr(toolbox_client, "client", lambda: fake)
    seen = _script(monkeypatch, [
        {"content": "", "tool_calls": [_tc("toolbox_need", {"intent": "a"})]},
        {"content": "", "tool_calls": [_tc("toolbox_need", {"intent": "b"})]},
        {"content": "", "tool_calls": [_tc("respond", {"reply": "ok", "commands": []})]},
    ])
    out = brain.respond_with_tools("loop please", LLM, {"enabled": True, "max_steps": 2})
    assert out["reply"] == "ok"
    names = [t["function"]["name"] for t in seen[-1]["tools"]]
    assert names == ["respond"]


def test_offline_falls_back_with_note(monkeypatch):
    monkeypatch.setattr(toolbox_client, "client", lambda: FakeToolBox(up=False))
    captured = {}

    def fake(host, path, body, timeout):
        if path == "/api/show":
            return {"capabilities": ["tools"]}
        captured["system"] = body["messages"][0]["content"]
        return {"message": {"content": json.dumps({"reply": "I can't reach ToolBox right now.", "commands": []})}}
    monkeypatch.setattr(llm_providers, "_ollama_request", fake)
    out = brain.respond_with_tools("anything in my inbox?", LLM, {"enabled": True})
    assert out["toolbox"]["state"] == "offline"
    assert "unreachable" in captured["system"]
    assert out["reply"].startswith("I can't reach ToolBox")


def test_model_without_tools_is_unsupported(monkeypatch):
    def fake(host, path, body, timeout):
        if path == "/api/show":
            return {"capabilities": ["completion"]}
        return {"message": {"content": json.dumps({"reply": "hi", "commands": []})}}
    monkeypatch.setattr(llm_providers, "_ollama_request", fake)
    out = brain.respond_with_tools("hello", LLM, {"enabled": True})
    assert out["toolbox"]["state"] == "unsupported"
    assert out["reply"] == "hi"


def test_rigel_commands_still_come_through(monkeypatch):
    monkeypatch.setattr(toolbox_client, "client", lambda: FakeToolBox())
    _script(monkeypatch, [{"content": "", "tool_calls": [_tc("respond", {
        "reply": "Waiting on approval.", "commands": [{"action": "open_app", "args_json": "{\"target\": \"Safari\"}"}]})]}])
    out = brain.respond_with_tools("open Safari", LLM, {"enabled": True})
    assert out["commands"] == [{"action": "open_app", "args": {"target": "Safari"}}]


def test_disabled_uses_plain_brain(monkeypatch):
    def fake(host, path, body, timeout):
        assert path != "/api/show"
        return {"message": {"content": json.dumps({"reply": "plain", "commands": []})}}
    monkeypatch.setattr(llm_providers, "_ollama_request", fake)
    out = brain.respond_with_tools("hello", LLM, {"enabled": False})
    assert out["toolbox"]["state"] == "disabled" and out["reply"] == "plain"


def test_guessed_tool_name_is_not_run_and_gets_real_matches(monkeypatch):
    """Regression (live, llama3.1:8b, 2026-11-15): the model skipped need and
    called 'system health'. Rigel must not forward an unseen name; it looks it
    up and hands the real matches back."""
    fake = FakeToolBox()
    monkeypatch.setattr(toolbox_client, "client", lambda: fake)
    seen = _script(monkeypatch, [
        {"content": "", "tool_calls": [_tc("toolbox_call", {"tool": "system health", "arguments": {}})]},
        {"content": "", "tool_calls": [_tc("toolbox_call", {"tool": "osa-system.health.battery", "arguments": {}})]},
        {"content": "", "tool_calls": [_tc("respond", {"reply": "Battery is full.", "commands": []})]},
    ])
    out = brain.respond_with_tools("how's my battery?", LLM, {"enabled": True})
    assert fake.calls == [("need", "system health"), ("call", "osa-system.health.battery")]
    assert "osa-system.health.battery" in seen[1]["messages"][-1]["content"]
    assert out["reply"] == "Battery is full."


def test_stray_arguments_are_folded_in():
    """Regression (live, llama3.1:8b): {'tool': ..., 'path': ...} without 'arguments'."""
    assert tool_brain._call_arguments({"tool": "osa-system.fs.delete", "path": "/tmp/x"}) == {"path": "/tmp/x"}
    assert tool_brain._call_arguments({"tool": "t", "arguments": "{\"a\": 1}"}) == {"a": 1}
    assert tool_brain._call_arguments({"tool": "t", "arguments": {"a": 1}, "a": 2}) == {"a": 1}


def test_tool_call_written_as_text_is_executed(monkeypatch):
    """Regression (live, llama3.1:8b): the model replied with a JSON tool call as text."""
    fake = FakeToolBox()
    monkeypatch.setattr(toolbox_client, "client", lambda: fake)
    _script(monkeypatch, [
        {"content": "", "tool_calls": [_tc("toolbox_need", {"intent": "battery"})]},
        {"content": 'Sure. {"name": "toolbox_call", "parameters": {"tool": "osa-system.health.battery"}}'},
        {"content": "", "tool_calls": [_tc("respond", {"reply": "Full.", "commands": []})]},
    ])
    out = brain.respond_with_tools("battery?", LLM, {"enabled": True})
    assert ("call", "osa-system.health.battery") in fake.calls
    assert out["reply"] == "Full."


def test_text_tool_call_only_accepts_our_tools():
    assert tool_brain._text_tool_call('{"name": "rm_rf", "parameters": {}}') is None
    assert tool_brain._text_tool_call("plain words") is None


def test_need_query_drops_paths():
    """Regression (live): 'delete file /Users/…/x.txt' matched 0 tools in ToolBox."""
    assert tool_brain._clean_intent("delete file /Users/t/Codehome/x.txt") == "delete file"
    assert tool_brain._clean_intent("read '~/notes/a b.md' please") == "read please"
    assert tool_brain._clean_intent("/only/a/path") == "/only/a/path"


def test_punctuation_only_guess_is_corrected_to_the_real_tool(monkeypatch):
    """Regression (live, llama3.1:8b): guessed 'osa-system fs delete'."""
    fake = FakeToolBox()
    fake.need = lambda url, intent, limit=8: (json.dumps({"matches": [{"tool": "osa-system.fs.delete"}]}), False)
    monkeypatch.setattr(toolbox_client, "client", lambda: fake)
    _script(monkeypatch, [
        {"content": "", "tool_calls": [_tc("toolbox_call", {"tool": "osa-system fs delete", "path": "/tmp/x"})]},
        {"content": "", "tool_calls": [_tc("respond", {"reply": "Deleted.", "commands": []})]},
    ])
    out = brain.respond_with_tools("delete /tmp/x", LLM, {"enabled": True})
    assert fake.calls == [("call", "osa-system.fs.delete")]
    assert out["tool_steps"][-1]["arguments"] == {"path": "/tmp/x"}


def _step(status="ok", via=None):
    return tool_brain.ToolStep(kind="call", tool="osa-system.fs.delete", arguments={}, status=status, ms=1,
                               approval={"status": "approved", "answered_via": via} if via else None)


def test_sanitize_replaces_false_pending_claim_with_facts():
    """Regression (live, llama3.1:8b): reply claimed 'waiting on your approval' and leaked respond(...)."""
    reply = ("Understood. I've logged that and I'm waiting on your approval to delete the file — check the console.\n\n"
             "respond(commands=[{\"target\": \"delete_file\"}])")
    out = tool_brain._sanitize_reply(reply, [], [_step(via="voice")])
    assert out == "Done: fs delete ran after you approved it by voice."


def test_sanitize_keeps_good_replies_and_drops_only_leaks():
    assert tool_brain._sanitize_reply("Battery is at 100%.", [], [_step()]) == "Battery is at 100%."
    assert tool_brain._sanitize_reply('Done.\n{"name": "toolbox_call"}', [], [_step()]) == "Done."
    # A real pending Rigel command keeps its approval line.
    line = "Understood. I'm waiting on your approval to open Safari — check the console."
    assert tool_brain._sanitize_reply(line, [{"action": "open_app"}], []) == line


def test_sanitize_reports_declined():
    assert "wasn't approved" in tool_brain._sanitize_reply("", [], [_step(status="declined")])


def test_found_but_not_called_gets_one_nudge(monkeypatch):
    """Regression (live, llama3.1:8b): need found fs.delete, then 'I've called it' with no call."""
    fake = FakeToolBox()
    monkeypatch.setattr(toolbox_client, "client", lambda: fake)
    seen = _script(monkeypatch, [
        {"content": "", "tool_calls": [_tc("toolbox_need", {"intent": "battery"})]},
        {"content": "I've called osa-system.health.battery for you."},
        {"content": "", "tool_calls": [_tc("toolbox_call", {"tool": "osa-system.health.battery"})]},
        {"content": "", "tool_calls": [_tc("respond", {"reply": "Full.", "commands": []})]},
    ])
    out = brain.respond_with_tools("battery?", LLM, {"enabled": True})
    assert out["reply"] == "Full."
    assert any(m["role"] == "user" and "haven't run any tool" in m["content"] for m in seen[2]["messages"])


def test_claimed_action_without_a_call_is_replaced():
    out = tool_brain._sanitize_reply("I've called osa-system.fs.delete with the path. Please approve.", [], [])
    assert "didn't actually run it" in out
    assert tool_brain._sanitize_reply("I couldn't find a tool for that.", [], []) == "I couldn't find a tool for that."
