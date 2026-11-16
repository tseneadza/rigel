"""Menu-action matching must ignore the target app's own name (live bug
2026-11-16: "copy this in TextEdit" matched the TextEdit app menu)."""
from sidecar import brain
from sidecar.handlers import menu_actions

TEXTEDIT_MENU = [
    ["TextEdit", "About TextEdit"],
    ["TextEdit", "Settings…"],
    ["TextEdit", "Services"],
    ["TextEdit", "Show All"],
    ["File", "New"],
    ["Edit", "Copy"],
    ["Format", "Font", "Show Fonts"],
    ["Format", "Font", "Show Colors"],
]


def _commands(monkeypatch, text):
    monkeypatch.setattr(menu_actions, "list_running_apps", lambda: ["TextEdit", "Finder"])
    monkeypatch.setattr(menu_actions, "discover_menu", lambda app: TEXTEDIT_MENU)
    return brain._menu_action_commands(text)


def test_app_name_does_not_pull_in_the_app_menu(monkeypatch):
    for text, expected in [
        ("copy this in TextEdit", ["Edit", "Copy"]),
        ("new document in TextEdit", ["File", "New"]),
        ("show fonts in TextEdit", ["Format", "Font", "Show Fonts"]),
    ]:
        commands, note = _commands(monkeypatch, text)
        assert note is None, (text, note)
        assert commands == [
            {"action": "click_menu_item", "args": {"app": "TextEdit", "menu_path": expected}}
        ], text


def test_strip_is_whole_word_and_case_insensitive():
    assert brain._without_app_name("Copy in TEXTEDIT", "TextEdit").split() == ["Copy", "in"]
    assert "Notes" in brain._without_app_name("Notesy Notes", "Note")
