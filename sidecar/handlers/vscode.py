"""Visual Studio Code app handler.

VS Code doesn't expose a rich AppleScript dictionary the way an app like
Chrome does — its scriptable surface is essentially nonexistent — but it
ships a first-class CLI (``code``) built for exactly this kind of external
scripting: opening a file, a folder-as-workspace, or a fresh window from
outside the app. We shell out to that CLI for every VS-Code-specific action
instead of fighting AppleScript for something it was never designed to do.
"Front the window"/"minimize it" carry no VS-Code-specific behavior at all,
so those two still go through the shared ``window_ops`` AppleScript helpers
rather than duplicating that logic here.

This handler deliberately does *not* expose a generic "open VS Code" or
"quit VS Code" action. Launching/quitting the whole app is ``executor.py``'s
``open_app``/``close_app`` path, matched by ``brain.py``'s shared four-verb
pass before an utterance ever reaches a handler's own scoped LLM call. This
handler only covers what happens *inside* VS Code once it's running (or
being launched fresh): which file or folder ends up open, whether a new
window appears.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from sidecar.handlers import registry, window_ops
from sidecar.handlers.base import AppHandler

# System Events' process name for VS Code's main process — this is the
# executable name inside "Visual Studio Code.app/Contents/MacOS", which
# Microsoft ships as "Code", *not* the "Visual Studio Code" display name
# the Finder/Dock/Info.plist (CFBundleName) show. Activity Monitor confirms
# the same: the running process lists as "Code" (plus several "Code Helper"
# children), never as "Visual Studio Code". If ``focus``/``minimize`` ever
# report success but nothing visibly happens, confirm this on the target
# machine with VS Code running:
#   osascript -e 'tell application "System Events" to name of every process'
_PROCESS_NAME = "Code"

_CLI_MISSING = (
    "the 'code' CLI isn't on PATH — install it from VS Code's Command Palette: "
    "Shell Command: Install 'code' command in PATH."
)


def _run_code(args: list[str], ok_detail: str) -> tuple[str, str]:
    """Run ``code <args>``, translating the common failure modes (CLI not on
    PATH, non-zero exit) into ``(status, detail)`` rather than a traceback."""
    try:
        result = subprocess.run(["code", *args], capture_output=True, text=True)
    except FileNotFoundError:
        return ("error", _CLI_MISSING)
    if result.returncode != 0:
        return ("error", result.stderr.strip() or f"'code {' '.join(args)}' failed.")
    return ("ok", ok_detail)


def _open_target(tool_input: dict, kind: str) -> tuple[str, str]:
    """Shared body of ``open_file``/``open_folder`` — the ``code`` CLI tells
    the two apart itself based on what the path resolves to, so the only
    difference between the two tools is the error wording."""
    raw = str(tool_input.get("path", "")).strip()
    if not raw:
        return ("error", f"no {kind} path given.")
    target = Path(raw).expanduser()
    return _run_code([str(target)], f"Opened {target} in VS Code.")


class VSCodeHandler(AppHandler):
    """Operates an already-running (or freshly launched) VS Code: what's
    shown inside it, not whether it's running at all."""

    app_id = "vscode"
    display_name = "Visual Studio Code"
    match_keywords = ["vs code", "vscode", "visual studio code"]

    system_prompt = (
        "You control Visual Studio Code for Rigel, a voice-activated desktop "
        "assistant. The user has already spoken a request that mentions VS "
        "Code; decide whether it asks for one of your specific in-app "
        "actions and, if so, call exactly that one tool.\n\n"
        "Your tools cover what VS Code shows once it's running: opening a "
        "particular file, opening a particular folder as a workspace, "
        "opening a new empty window, bringing VS Code to the front, or "
        "minimizing it. They do NOT cover launching or quitting VS Code "
        "itself — that is handled elsewhere, by a separate generic "
        "open-app/close-app path. If the user just says something like "
        "\"open VS Code\" or \"quit VS Code\" with no file, folder, or "
        "window action attached, call no tool at all and let that other "
        "path handle it. Only call a tool when the request is clearly "
        "about what VS Code should show or do internally."
    )

    tools = [
        {
            "name": "open_file",
            "description": (
                "Open a specific file in VS Code, in the current window if one "
                "is already open. Works for a file that doesn't exist yet, too."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Path to the file to open, e.g. '~/projects/app/main.py'. "
                            "'~' is expanded automatically."
                        ),
                    }
                },
                "required": ["path"],
            },
        },
        {
            "name": "open_folder",
            "description": "Open a folder in VS Code as a workspace.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Path to the folder to open, e.g. '~/projects/app'. "
                            "'~' is expanded automatically."
                        ),
                    }
                },
                "required": ["path"],
            },
        },
        {
            "name": "new_window",
            "description": "Open a new, empty VS Code window with no file or folder loaded.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "focus",
            "description": "Bring VS Code's window to the front. VS Code must already be running.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "minimize",
            "description": "Minimize all of VS Code's open windows to the Dock.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
    ]

    def execute_tool(self, tool_name: str, tool_input: dict) -> tuple[str, str]:
        if tool_name == "open_file":
            return _open_target(tool_input, "file")
        if tool_name == "open_folder":
            return _open_target(tool_input, "folder")
        if tool_name == "new_window":
            return _run_code(["--new-window"], "Opened a new VS Code window.")
        if tool_name == "focus":
            return window_ops.focus(_PROCESS_NAME)
        if tool_name == "minimize":
            return window_ops.minimize(_PROCESS_NAME)
        return ("error", f"'{tool_name}' is not a recognized VS Code action.")


registry.register(VSCodeHandler())
