"""Dynamic app-menu discovery — Slices 1-3 of App Menu Actions.

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

``list_running_apps()`` (Slice 2) lives here too — it's the same kind of
System Events query as ``frontmost_app()``, just "every foreground process"
instead of "the frontmost one," and confirmed on real hardware to need no
Accessibility grant either (only walking a specific app's UI elements, as
``discover_menu()`` does, requires it).

``fuzzy_match()`` (Slice 3) is the last read-only piece: matching a spoken
phrase against a discovered menu's real item labels by word-token overlap,
stdlib-only (``re``, matching this repo's no-casual-new-deps convention).
Still no clicking — ``sidecar/brain.py`` uses this to report what it
*would* click, not to click it.

``click_menu_item()`` (Slice 4) is the only function in this module that
actually acts: given a menu path already discovered and matched, click it
for real. Unlike ``discover_menu()``/``frontmost_app()``/
``list_running_apps()``, which *raise* ``MenuDiscoveryError`` (they're
called from ``brain.py``'s command-detection phase, before anything is
logged or approved), ``click_menu_item()`` follows ``executor.py``'s
``(status, detail)``-tuple, never-raises contract instead — it's called
from ``executor.execute()``, alongside every other action's execution
path, and by the time it runs the click has already been through preview
and approval. ``is_dangerous()`` is the other Slice 4 piece:
``executor.is_whitelisted()`` consults it before anything else, and a
dangerous-sounding item always requires approval — even with the app's
whitelist entry set to ``all: true``.
"""
from __future__ import annotations

import re
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
    """Run ``osascript``, translating "not on this machine at all" (no
    macOS — e.g. developing on Linux, as this repo's own sessions
    sometimes do) into the same raised-error contract as every other
    failure here, instead of a raw ``FileNotFoundError`` traceback."""
    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    except FileNotFoundError as e:
        raise MenuDiscoveryError(
            "'osascript' isn't available on this machine — App Menu Actions "
            "is macOS-only, same as the rest of Rigel's execution layer."
        ) from e
    return result.stdout, result.stderr, result.returncode


def _permission_denied(stderr: str) -> bool:
    # macOS reports this as error -1719 ("not allowed assistive access") or
    # occasionally -25211/1002 depending on OS version and what's being
    # queried; matching on the human-readable phrase is more stable across
    # versions than pinning one error code.
    lowered = stderr.lower()
    return "not allowed assistive access" in lowered or "-1719" in stderr


def _process_not_found(stderr: str) -> bool:
    # System Events reports this as error -1728 ("Can't get process
    # <name>") when no process by that name is running — confirmed live
    # against a not-currently-running Safari. Distinct from a permission
    # error, so it gets its own clean message rather than falling through
    # to raw AppleScript text.
    return "-1728" in stderr


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


def list_running_apps() -> list[str]:
    """Every foreground (non-background-only) running app's process name —
    the same identifiers ``frontmost_app()``/``discover_menu()`` use.

    Raises ``MenuDiscoveryError`` on failure, same as the rest of this
    module — confirmed on real hardware this call needs no Accessibility
    grant (see ``frontmost_app()``'s docstring), but the check is kept for
    the same reason it's kept there: a future macOS version tightening
    what counts as "assistive access" shouldn't surface as a raw
    AppleScript error.
    """
    script = (
        'tell application "System Events" to set appList to name of every '
        'process whose background only is false\n'
        "set AppleScript's text item delimiters to linefeed\n"
        "return appList as text"
    )
    stdout, stderr, returncode = _run_osascript(script)
    if returncode != 0:
        if _permission_denied(stderr):
            raise MenuDiscoveryError(
                "Rigel doesn't have Accessibility permission yet — grant it in "
                "System Settings -> Privacy & Security -> Accessibility, then retry."
            )
        raise MenuDiscoveryError(stderr.strip() or "failed to list running apps.")
    return [name for name in stdout.splitlines() if name.strip()]


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
        if _process_not_found(stderr):
            raise MenuDiscoveryError(f"'{app_name}' isn't running.")
        raise MenuDiscoveryError(stderr.strip() or f"failed to discover {app_name}'s menu bar.")
    lines = [line for line in stdout.splitlines() if line.strip()]
    return [line.split("|||") for line in lines]


# fuzzy_match() scores by word-token overlap, not raw character similarity
# (difflib.SequenceMatcher.ratio() over full strings). Tried that first —
# it degrades badly once the phrase includes words the menu label doesn't
# have (very common: the app name itself, "please", filler), diluting the
# ratio against the candidate's short label. A "partial ratio" (best
# character match over any same-length window) fixes the dilution but
# picks up spurious cross-word character coincidences instead (verified
# live: "minimize the textedit window" ranked "Edit > Copy" above "Window
# > Minimize" on pure character overlap). Token overlap doesn't have either
# problem: it asks "how many of this menu item's own distinctive words did
# the user actually say," which is what the phrase should be judged on.
_STOPWORDS = frozenset({
    "the", "a", "an", "this", "that", "these", "those", "in", "on", "to",
    "of", "for", "my", "please", "now", "it", "its", "me", "and", "or",
})

# Fraction of a candidate's own (non-stopword) words that must appear in
# the phrase to count as a match at all — an unrelated candidate can still
# share a stray common word, so a floor keeps that from being reported as
# a guess. Ties within tie_margin of the top score are all returned rather
# than arbitrarily picking one, per the ambiguous-match open question in
# docs/proposals/menu-actions.md — Slice 3 only *reports* an ambiguous
# match rather than resolving it (nothing here executes anything yet).
_FUZZY_MATCH_THRESHOLD = 0.5
_FUZZY_MATCH_TIE_MARGIN = 0.15
_FUZZY_MATCH_MAX_CANDIDATES = 3


def _tokenize(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOPWORDS}


def fuzzy_match(
    phrase: str, menu_paths: list[list[str]]
) -> list[tuple[list[str], float]]:
    """Rank ``menu_paths`` (as returned by ``discover_menu()``) by what
    fraction of each path's own distinctive words (e.g. ``{"new",
    "window"}`` for ``["File", "New Window"]``, ignoring stopwords like
    "the") also appear in ``phrase``.

    Returns an empty list if nothing clears ``_FUZZY_MATCH_THRESHOLD`` — a
    low-confidence guess is worse than admitting no match, since a future
    slice will eventually execute whatever this returns. Otherwise returns
    the top match plus any others within ``_FUZZY_MATCH_TIE_MARGIN`` of its
    score (capped at ``_FUZZY_MATCH_MAX_CANDIDATES``), sorted best-first —
    more than one entry means the phrase was genuinely ambiguous, not that
    the caller should just take ``[0]``.
    """
    if not menu_paths:
        return []
    phrase_words = _tokenize(phrase)
    if not phrase_words:
        return []
    scored = []
    for path in menu_paths:
        candidate_words = _tokenize(" ".join(path))
        if not candidate_words:
            continue
        ratio = len(candidate_words & phrase_words) / len(candidate_words)
        scored.append((path, ratio))
    if not scored:
        return []
    scored.sort(key=lambda item: item[1], reverse=True)
    top_ratio = scored[0][1]
    if top_ratio < _FUZZY_MATCH_THRESHOLD:
        return []
    return [item for item in scored if top_ratio - item[1] <= _FUZZY_MATCH_TIE_MARGIN][
        :_FUZZY_MATCH_MAX_CANDIDATES
    ]


# Checked case-insensitively against a menu path's full joined text, so a
# multi-word phrase like "empty trash" matches regardless of which segment
# it lands in, and a single-word item like "Quit" or "Reset" still matches
# even though real apps also use these words in harmless contexts ("Reset
# Zoom", "Quit and Keep Windows") — the list is deliberately conservative
# (over-block rather than under-block), since the cost of a false positive
# here is "approve one extra time," not "silently ran something risky."
_DANGEROUS_KEYWORDS = frozenset({
    "delete", "erase", "empty trash", "format", "quit", "uninstall",
    "remove", "discard", "reset", "wipe", "destroy",
})


def is_dangerous(menu_path: list[str]) -> bool:
    """True if any word/phrase in ``_DANGEROUS_KEYWORDS`` appears anywhere
    in ``menu_path``'s joined text. ``executor.is_whitelisted()`` treats
    this as an unconditional override — see this module's docstring."""
    haystack = " ".join(menu_path).lower()
    return any(keyword in haystack for keyword in _DANGEROUS_KEYWORDS)


def _click_menu_item_script(app_name: str, menu_path: list[str]) -> str:
    """Build the nested ``menu item "X" of menu 1 of ...`` AppleScript
    reference matching ``menu_path``'s exact depth — the standard macOS
    scripting idiom for reaching a specific (possibly nested) menu item by
    name, mirroring the same ancestor chain ``discover_menu()``'s own walk
    used to find it (``menu 1 of <parent>`` at every level)."""
    leaf = _quote(menu_path[-1])
    ancestors = menu_path[:-1]
    ref = f"menu bar item {_quote(ancestors[0])} of menu bar 1"
    for name in ancestors[1:]:
        ref = f"menu item {_quote(name)} of menu 1 of {ref}"
    target = f"menu item {leaf} of menu 1 of {ref}"
    return f'tell application "System Events" to tell process {_quote(app_name)} to click {target}'


def click_menu_item(app_name: str, menu_path: list[str]) -> tuple[str, str]:
    """Click the menu item at ``menu_path`` (as returned by
    ``discover_menu()``/matched by ``fuzzy_match()``) in ``app_name``.

    Returns ``(status, detail)`` with ``status`` one of ``'ok' | 'error'``
    — never raises, matching ``executor._execute_macos``'s contract (see
    this module's docstring for why this function differs from the rest
    of the module on that point). Does not re-verify the path still exists
    before clicking — by the time this runs, the path was already
    discovered live and matched against the user's own phrase; a stale
    path (app quit, menu changed) surfaces as an ordinary AppleScript
    error below, same as any other execution failure.
    """
    if not menu_path:
        return ("error", "no menu path given.")
    script = _click_menu_item_script(app_name, menu_path)
    try:
        stdout, stderr, returncode = _run_osascript(script)
    except MenuDiscoveryError as e:
        # _run_osascript raises for "osascript isn't on this machine at
        # all" — every other function in this module lets that propagate
        # (they're called before anything is logged/approved), but this
        # one is an executor.execute() path and must never raise.
        return ("error", str(e))
    if returncode != 0:
        if _permission_denied(stderr):
            return (
                "error",
                "Rigel doesn't have Accessibility permission yet — grant it in "
                "System Settings -> Privacy & Security -> Accessibility, then retry.",
            )
        if _process_not_found(stderr):
            return ("error", f"'{app_name}' isn't running.")
        return ("error", stderr.strip() or f"failed to click {' > '.join(menu_path)} in {app_name}.")
    return ("ok", f"Clicked {' > '.join(menu_path)} in {app_name}.")


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
