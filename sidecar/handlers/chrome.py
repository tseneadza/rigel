"""``ChromeHandler`` — Rigel's app handler for Google Chrome.

Unlike the generic ``open_app``/``close_app`` verbs in ``executor.py``, this
handler speaks Chrome's *own* AppleScript dictionary — tabs and windows are
first-class objects Chrome exposes directly (``tell application "Google
Chrome" to ...``), so there's no need to drive it through System Events the
way app-agnostic window operations do (see ``window_ops.py``). Only
``focus``/``minimize`` delegate there, since "bring this app's window
forward" is the same for every app and ``window_ops`` already owns it.

This handler deliberately does *not* expose "open Chrome" or "quit Chrome"
tools — launching/terminating the whole application is the generic
``open_app``/``close_app`` path's job (``brain.py``'s shared four-verb pass
handles it before an utterance ever reaches a per-app handler). Everything
here is about acting *inside* an already-running (or about-to-be-launched-
by-``activate``) Chrome.
"""
from __future__ import annotations

import subprocess

from sidecar.handlers import registry, window_ops
from sidecar.handlers.base import AppHandler


def _run_chrome_script(script: str) -> tuple[str, str, str]:
    """Run an AppleScript snippet via ``osascript``, matching the shell-out
    pattern ``executor._execute_macos`` and ``window_ops`` use elsewhere.
    Returns ``(status, stdout, stderr)`` rather than window_ops's collapsed
    ``tuple[str, str] | None`` shape, because ``list_tabs`` needs stdout as
    its actual answer, not just a success/failure signal."""
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    status = "ok" if result.returncode == 0 else "error"
    return status, result.stdout.strip(), result.stderr.strip()


def _as_applescript_string(value: str) -> str:
    """Quote ``value`` as an AppleScript string literal. URLs are the only
    user-influenced strings interpolated into a script here, so this only
    needs to survive a stray quote or backslash, not full AppleScript
    escaping."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


class ChromeHandler(AppHandler):
    """Tabs and windows for an already-running (or about-to-launch) Chrome.

    Stateless singleton — see the module-level ``register()`` call at the
    bottom of this file, and ``AppHandler``'s docstring for why that's safe.
    """

    app_id = "chrome"
    display_name = "Google Chrome"
    match_keywords = ["chrome", "google chrome"]

    system_prompt = (
        "You control Google Chrome for Rigel, a voice-activated desktop "
        "agent. The user's utterance has already been routed to you because "
        "it mentioned Chrome specifically — your only job is deciding "
        "whether it maps to one of your tools, and if so, calling exactly "
        "that one tool with whatever arguments it needs. Your tools cover "
        "in-app tab and window operations only: opening or closing a tab, "
        "listing open tabs, opening a new window, and focusing or "
        "minimizing Chrome. If the request is actually about launching or "
        "quitting the whole Chrome application (e.g. 'open Chrome', 'quit "
        "Chrome', 'start Chrome') — not something happening inside it — "
        "call nothing; that's handled elsewhere, by Rigel's generic "
        "open_app/close_app path, not by you. If the request doesn't "
        "clearly match any of your tools, also call nothing rather than "
        "guessing."
    )

    tools = [
        {
            "name": "new_tab",
            "description": (
                "Open a new tab in Chrome's frontmost window (launching Chrome "
                "and/or opening a window first if none exists), optionally "
                "navigating it to a URL."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": (
                            "URL to load in the new tab, e.g. 'https://example.com'. "
                            "Omit to open Chrome's default new-tab page."
                        ),
                    },
                },
                "required": [],
            },
        },
        {
            "name": "close_tab",
            "description": "Close the active tab in Chrome's frontmost window.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "list_tabs",
            "description": (
                "List the title and URL of every tab open in Chrome's frontmost "
                "window. Use this to answer questions like 'what tabs do I have "
                "open' — its result text is the answer, not just a status."
            ),
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "new_window",
            "description": (
                "Open a new Chrome window, optionally navigating its first tab "
                "to a URL."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": (
                            "URL to load in the new window's first tab, e.g. "
                            "'https://example.com'. Omit to open Chrome's default "
                            "new-tab page."
                        ),
                    },
                },
                "required": [],
            },
        },
        {
            "name": "focus",
            "description": "Bring Chrome's window to the front.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "minimize",
            "description": "Minimize all of Chrome's open windows.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
    ]

    def execute_tool(self, tool_name: str, tool_input: dict) -> tuple[str, str]:
        if tool_name == "new_tab":
            return self._new_tab(tool_input.get("url"))
        if tool_name == "close_tab":
            return self._close_tab()
        if tool_name == "list_tabs":
            return self._list_tabs()
        if tool_name == "new_window":
            return self._new_window(tool_input.get("url"))
        if tool_name == "focus":
            return window_ops.focus(self.display_name)
        if tool_name == "minimize":
            return window_ops.minimize(self.display_name)
        return ("error", f"'{tool_name}' is not a recognized Chrome action.")

    def _new_tab(self, url: str | None) -> tuple[str, str]:
        url = (url or "").strip()
        properties = f" with properties {{URL:{_as_applescript_string(url)}}}" if url else ""
        script = (
            'tell application "Google Chrome"\n'
            "    activate\n"
            "    if (count of windows) = 0 then\n"
            "        make new window\n"
            "    end if\n"
            f"    tell window 1 to make new tab{properties} at end of tabs\n"
            "end tell"
        )
        status, _, stderr = _run_chrome_script(script)
        if status == "error":
            return ("error", stderr or "failed to open a new tab.")
        return ("ok", f"Opened a new tab{f' at {url}' if url else ''}.")

    def _close_tab(self) -> tuple[str, str]:
        # "window 1" raises if Chrome has no window open, which reads as an
        # opaque AppleScript stack trace — check first so the user gets a
        # plain-English reason instead.
        if not window_ops.is_running(self.display_name):
            return ("error", "Chrome isn't running.")
        script = 'tell application "Google Chrome" to close active tab of window 1'
        status, _, stderr = _run_chrome_script(script)
        if status == "error":
            return ("error", stderr or "failed to close the active tab.")
        return ("ok", "Closed the active tab.")

    def _list_tabs(self) -> tuple[str, str]:
        if not window_ops.is_running(self.display_name):
            return ("error", "Chrome isn't running.")
        # There's no separate "read" channel back to the user for app_action
        # results — the detail string returned here *is* the answer Rigel
        # shows for "what tabs do I have open", so it lists title + URL per
        # tab rather than just a count.
        script = (
            'tell application "Google Chrome"\n'
            '    set tabInfo to ""\n'
            "    repeat with t in tabs of window 1\n"
            '        set tabInfo to tabInfo & (title of t) & " — " & (URL of t) & linefeed\n'
            "    end repeat\n"
            "end tell\n"
            "return tabInfo"
        )
        status, stdout, stderr = _run_chrome_script(script)
        if status == "error":
            return ("error", stderr or "failed to list tabs.")
        if not stdout:
            return ("ok", "Chrome's frontmost window has no tabs open.")
        return ("ok", stdout)

    def _new_window(self, url: str | None) -> tuple[str, str]:
        url = (url or "").strip()
        script_lines = [
            'tell application "Google Chrome"',
            "    activate",
            "    make new window",
        ]
        if url:
            script_lines.append(f"    set URL of active tab of window 1 to {_as_applescript_string(url)}")
        script_lines.append("end tell")
        status, _, stderr = _run_chrome_script("\n".join(script_lines))
        if status == "error":
            return ("error", stderr or "failed to open a new window.")
        return ("ok", f"Opened a new window{f' at {url}' if url else ''}.")


registry.register(ChromeHandler())
