"""Dynamic app-menu discovery — Slice 1 of App Menu Actions.

See ``docs/proposals/menu-actions.md`` for the full plan. This module is
deliberately narrow: it can find the frontmost app and enumerate a running
app's real menu-bar items via the macOS Accessibility API (through System
Events), and nothing else yet. No fuzzy matching (Slice 3), no clicking
(Slice 4), and it isn't imported by ``brain.py``/``executor.py`` — the
whole point of doing this as its own slice is to prove the Accessibility
permission model and the AX tree walk work at all, for an arbitrary app,
before anything gets wired into the approval-gated execution path.

Unlike ``chrome.py``'s AppleScript (Chrome exposes tabs/windows through its
*own* dictionary) or ``window_ops.py``'s System Events calls (which only
ever set one attribute), walking a menu bar means asking System Events
questions about a process it doesn't own and getting back a variable-shaped
answer — so failures are surfaced as a raised ``MenuDiscoveryError`` with a
specific, actionable message, rather than collapsed into an empty list a
caller could mistake for "this app genuinely has no menu items."

Requires Rigel's own process (or, for the standalone check below, whatever
terminal/interpreter runs it) to be granted Accessibility access: System
Settings -> Privacy & Security -> Accessibility. Without that grant, System
Events returns a permission error rather than menu data.

Try it directly on a Mac once Accessibility is granted:
    python3 -m sidecar.handlers.menu_actions            # frontmost app
    python3 -m sidecar.handlers.menu_actions "Safari"    # a named app
"""
from __future__ import annotations

import subprocess
import sys

# Submenu depth captured during discovery. Two levels (a menu bar item's own
# items, plus one level of submenu, e.g. File > Export > PDF) matches the
# fuzzy-match default proposed in docs/proposals/menu-actions.md; going
# deeper multiplies AppleScript round-trip cost for items a phrase is
# unlikely to reference. Revisit alongside Slice 3 if that default changes.
_MAX_SUBMENU_DEPTH = 2


class MenuDiscoveryError(Exception):
    """Raised when ``discover_menu()``/``frontmost_app()`` can't get a real
    answer from System Events — no Accessibility permission, the named app
    isn't running, or another AppleScript failure."""


def _quote(value: str) -> str:
    """Quote ``value`` as an AppleScript string literal — same minimal
    escaping ``chrome.py``'s ``_as_applescript_string`` uses, since an app
    name is the one piece of user-influenced text interpolated here."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _run_osascript(script: str) -> tuple[str, str, int]:
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return result.stdout, result.stderr, result.returncode


def _permission_denied(stderr: str) -> bool:
    # macOS reports this as error -1719 ("not allowed assistive access") or
    # occasionally -25211/1002 depending on OS version and what's being
    # queried; matching on the human-readable phrase is more stable across
    # versions than pinning one error code.
    lowered = stderr.lower()
    return "not allowed assistive access" in lowered or "-1719" in stderr


def frontmost_app() -> str | None:
    """Name of the frontmost app's process, e.g. ``"Google Chrome"``.

    Returns ``None`` if there's no frontmost app to report (nothing
    reasonable for a caller to act on); raises ``MenuDiscoveryError`` if
    System Events itself can't be reached (permission denied, not running).
    """
    script = 'tell application "System Events" to name of first process whose frontmost is true'
    stdout, stderr, returncode = _run_osascript(script)
    if returncode != 0:
        if _permission_denied(stderr):
            raise MenuDiscoveryError(
                "Rigel doesn't have Accessibility permission yet — grant it in "
                "System Settings -> Privacy & Security -> Accessibility, then retry."
            )
        raise MenuDiscoveryError(stderr.strip() or "failed to determine the frontmost app.")
    name = stdout.strip()
    return name or None


# Builds the recursive AX walk as an AppleScript string. Each discovered
# path becomes one output line, path segments joined by "|||" (chosen since
# it can't collide with a real menu label) so discover_menu() can split
# lines back into ["File", "Export", "PDF"]-shaped lists. Individual menu
# items are queried inside `try` blocks — some system-generated menus (the
# Apple menu, a Window menu with dynamic per-document entries) throw on
# specific items, and one bad item shouldn't blank out the whole walk.
_DISCOVER_MENU_SCRIPT = """
set outputLines to {{}}
tell application "System Events"
    tell process {app_name}
        tell menu bar 1
            repeat with topMenu in menu bar items
                set topName to name of topMenu
                if topName is not missing value then
                    try
                        tell menu 1 of topMenu
                            repeat with itemEl in menu items
                                set itemName to name of itemEl
                                if itemName is not missing value then
                                    set end of outputLines to topName & "|||" & itemName
                                    if (count of menus of itemEl) > 0 then
                                        try
                                            tell menu 1 of itemEl
                                                repeat with subEl in menu items
                                                    set subName to name of subEl
                                                    if subName is not missing value then
                                                        set end of outputLines to topName & "|||" & itemName & "|||" & subName
                                                    end if
                                                end repeat
                                            end tell
                                        end try
                                    end if
                                end if
                            end repeat
                        end tell
                    end try
                end if
            end repeat
        end tell
    end tell
end tell
set AppleScript's text item delimiters to linefeed
return outputLines as text
"""


def discover_menu(app_name: str) -> list[list[str]]:
    """Enumerate ``app_name``'s real menu-bar items, up to
    ``_MAX_SUBMENU_DEPTH`` levels deep, as a list of paths — e.g.
    ``[["File", "New Window"], ["File", "Export", "PDF"], ...]``.

    ``app_name`` must be the app's System Events process name (what
    ``frontmost_app()``/``list_running_apps()`` return), which is not
    always its display name — see ``vscode.py``'s ``_PROCESS_NAME`` for a
    concrete case where they differ.

    Raises ``MenuDiscoveryError`` on any failure: no Accessibility
    permission, the app isn't running, or another AppleScript error. Never
    returns an empty list to mean "failed" — an empty list means the walk
    genuinely found no menu items, which a caller can trust.
    """
    script = _DISCOVER_MENU_SCRIPT.format(app_name=_quote(app_name))
    stdout, stderr, returncode = _run_osascript(script)
    if returncode != 0:
        if _permission_denied(stderr):
            raise MenuDiscoveryError(
                "Rigel doesn't have Accessibility permission yet — grant it in "
                "System Settings -> Privacy & Security -> Accessibility, then retry."
            )
        raise MenuDiscoveryError(stderr.strip() or f"failed to discover {app_name}'s menu bar.")
    lines = [line for line in stdout.splitlines() if line.strip()]
    return [line.split("|||") for line in lines]


def _main() -> None:
    app_name = sys.argv[1] if len(sys.argv) > 1 else None
    if app_name is None:
        app_name = frontmost_app()
        if app_name is None:
            print("No frontmost app found.")
            return
        print(f"(frontmost app: {app_name})")

    paths = discover_menu(app_name)
    print(f"{len(paths)} menu item(s) found for {app_name}:")
    for path in paths:
        print("  " + " > ".join(path))


if __name__ == "__main__":
    try:
        _main()
    except MenuDiscoveryError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
