"""A handler's app_action replaces a generic open_app for the same app
(live 2026-11-16: "open a new Chrome tab to github.com" asked for two
approvals)."""
from sidecar import brain, llm_providers

CFG = {"provider": "claude", "claude_model": "m"}


def _handler_returns(monkeypatch, commands):
    monkeypatch.setattr(llm_providers, "claude_app_action", lambda text, model, handler: commands)


def test_open_app_for_the_handled_app_is_dropped(monkeypatch):
    tab = {"action": "app_action", "args": {"app_id": "chrome", "tool": "new_tab", "tool_args": {}}}
    _handler_returns(monkeypatch, [tab])
    brain_cmds = [{"action": "open_app", "args": {"target": "Chrome"}}]
    assert brain._with_app_commands(brain_cmds, "open a new Chrome tab", CFG) == [tab]


def test_vscode_long_name_is_recognised(monkeypatch):
    focus = {"action": "app_action", "args": {"app_id": "vscode", "tool": "focus", "tool_args": {}}}
    _handler_returns(monkeypatch, [focus])
    brain_cmds = [{"action": "open_app", "args": {"target": "Visual Studio Code"}}]
    assert brain._with_app_commands(brain_cmds, "bring VS Code to the front", CFG) == [focus]


def test_other_commands_are_kept(monkeypatch):
    tab = {"action": "app_action", "args": {"app_id": "chrome", "tool": "new_tab", "tool_args": {}}}
    _handler_returns(monkeypatch, [tab])
    keep = [
        {"action": "open_app", "args": {"target": "Safari"}},
        {"action": "close_app", "args": {"target": "Chrome"}},
        {"action": "create_file", "args": {"target": "notes.txt"}},
    ]
    assert brain._with_app_commands(keep, "chrome tab and safari", CFG) == keep + [tab]


def test_no_handler_match_leaves_commands_alone(monkeypatch):
    called = []
    monkeypatch.setattr(llm_providers, "claude_app_action", lambda *a: called.append(a) or [])
    cmds = [{"action": "open_app", "args": {"target": "Chrome"}}]
    assert brain._with_app_commands(cmds, "open notes", CFG) == cmds
    assert called == []
