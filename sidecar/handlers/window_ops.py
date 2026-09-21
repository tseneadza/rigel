"""Shared window operations — the bits multiple app handlers need alike.

Every ``AppHandler`` supports its own app-specific actions (a new browser
tab, opening a folder in an editor, ...), but "bring this app's window to
the front" and "minimize it" are the same AppleScript regardless of which
app it is. Handlers call these instead of re-implementing them.

macOS only, matching the rest of the execution layer (``executor.py``'s
``_execute_macos``) — these are only ever reached through a handler's
``execute_tool``, which ``executor.execute()`` only calls after already
confirming ``sys.platform == "darwin"``.
"""
from __future__ import annotations

import subprocess


def _run_system_events(script: str) -> tuple[str, str] | None:
    """Run a System Events AppleScript snippet. Returns ``None`` on success
    so callers can supply their own success detail message; returns an
    ``('error', ...)`` tuple on failure."""
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        return ("error", result.stderr.strip() or "AppleScript command failed.")
    return None


def focus(app_name: str) -> tuple[str, str]:
    """Bring ``app_name``'s window to the front. The app must already be
    running — this doesn't launch it (that's ``open_app``'s job)."""
    script = f'tell application "System Events" to set frontmost of process "{app_name}" to true'
    failure = _run_system_events(script)
    return failure or ("ok", f"Focused {app_name}.")


def minimize(app_name: str) -> tuple[str, str]:
    """Minimize every one of ``app_name``'s open windows to the Dock."""
    script = (
        f'tell application "System Events" to tell process "{app_name}" '
        f'to set value of attribute "AXMinimized" of every window to true'
    )
    failure = _run_system_events(script)
    return failure or ("ok", f"Minimized {app_name}.")


def is_running(app_name: str) -> bool:
    """Best-effort check via System Events; treated as ``False`` on any
    AppleScript error (app not found, System Events unreachable, ...) rather
    than raising, since callers use this only to produce a friendlier error
    message, not to gate execution."""
    script = f'tell application "System Events" to (name of processes) contains "{app_name}"'
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return result.returncode == 0 and result.stdout.strip() == "true"
