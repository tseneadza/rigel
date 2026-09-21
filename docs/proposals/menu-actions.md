# Feature: App Menu Actions (Dynamic Menu-Bar Execution)

## Overview
Today Rigel's execution layer knows a small fixed verb list
(`open_app`/`close_app`/`create_file`/`delete_file`), plus, as of the
`AppHandler` framework in `sidecar/handlers/` (see
`docs/proposals/expanded-app-control.md`), two apps with their own
hand-written tool vocabularies (Chrome, VS Code). This feature goes further:
let Rigel click an app's **real menu-bar items** — dynamically discovered,
for *any* running app — instead of hand-wiring one intent per action
forever. Source: a scoping note captured 2026-09-19 ("Rigel Execution Layer
— App Menu Actions"), status `ready` there, most open questions already
resolved. This doc folds that note into the framework built since.

## Status
- [ ] Planned
- [x] In Development
- [ ] Incubating
- [ ] Alpha/Beta
- [ ] Production

*(Maps the source note's `status: ready` onto this repo's vocabulary; now
`In Development` — Slice 1 has landed, see Progress Log. That note lives
outside this repo and can't be written back to from here; update it
manually if you want its frontmatter to reflect this doc.)*

## Progress Log
- **Slice 1 landed**: `sidecar/handlers/menu_actions.py` —
  `frontmost_app()` and `discover_menu()`, both raising
  `MenuDiscoveryError` on failure (no Accessibility permission, app not
  running) rather than returning a silently-empty list. Deliberately not
  imported by `brain.py`/`executor.py`/`sidecar/handlers/__init__.py` yet —
  Slice 1 is standalone by design. Runnable directly on a Mac:
  `python3 -m sidecar.handlers.menu_actions ["App Name"]`
  (defaults to the frontmost app).
- **Slice 1 validated on real hardware.** After granting Accessibility
  permission (System Settings -> Privacy & Security -> Accessibility),
  `discover_menu("iTerm2")` correctly enumerated all 467 real menu items,
  including nested submenus to the intended depth (e.g. `Apple > Recent
  Items > Applications`). `frontmost_app()` needs no Accessibility grant at
  all (confirmed — it errored only once discovery, not frontmost
  detection, was attempted). Two rough edges found and fixed live against
  real error output: `osascript` missing entirely (this repo's own
  non-macOS dev sessions) now raises a clean `MenuDiscoveryError` instead
  of a raw `FileNotFoundError`; a named app that isn't running (error
  -1728, distinct from a permission error) now raises `"'<app>' isn't
  running."` instead of surfacing raw AppleScript text. The permission
  model, the AX tree walk, and both failure paths are now confirmed
  working end to end — Slice 2 is unblocked.
- **Slice 2 landed**: `menu_actions.list_running_apps()` (confirmed to need
  no Accessibility grant, same as `frontmost_app()`); `GET
  /api/rigel/running-apps` (503 with a clean message if System Events
  can't be reached, e.g. non-macOS); a direct, non-approval-gated "what
  apps are open" reply path in `brain.py` (`_running_apps_reply`, matched
  by `_RUNNING_APPS_QUERY` — checked before any provider call, since the
  answer is deterministic and needs no LLM); and a `RunningApps.jsx`
  dropdown in the orb window's header (next to Settings) showing the same
  list on demand. Not yet exercised on real hardware — the Python/FastAPI
  side is covered by the same kind of smoke test Slice 1 got (regex
  intercept, `TestClient` hitting `/running-apps`, confirmed to produce a
  clean 503 on this non-macOS environment), and the frontend build is
  clean, but the actual dropdown hasn't been clicked on a running Rigel
  yet.

## Architectural Decision — how this fits the `AppHandler` framework
This is the one thing the source note couldn't resolve, since it predates
`sidecar/handlers/`. Two ways to reconcile them:

**Recommended: menu actions are a generic fallback tier, not another
`AppHandler`.** An `AppHandler` subclass (`chrome.py`, `vscode.py`) declares
a *fixed* `tools` list at class-definition time — right for a well-known,
stable vocabulary, wrong for "whatever this app's menu bar currently
contains," which is dynamic and app-state-dependent (a greyed-out Edit menu
item, an app-specific submenu). So menu actions get their own module,
`sidecar/handlers/menu_actions.py`, matched not by `registry.match()`'s
keyword lookup but by a fallback step in `brain.py`: after the shared
four-verb pass *and* `registry.match()` (Chrome/VS Code) both come back
empty — or a matched handler's own scoped call returns no tool — resolve a
target app (named in the text, else frontmost) and try generic menu
discovery + fuzzy match against it. Named handlers stay the fast path for
actions with no menu equivalent (Chrome's `list_tabs` isn't a menu item);
menu actions become the universal safety net for everything else,
including apps nobody's written a handler for at all (Finder, Safari,
Slack, ...) — exactly the note's "not a fixed hardcoded list" goal.

**Rejected for v1: make menu actions the only mechanism, retire Chrome/VS
Code's custom tools.** A live AX tree walk + fuzzy match is slower and less
precise than a hand-declared tool for an app's common actions, and can't
express actions with no menu equivalent. Custom handlers stay worth writing
for apps Rigel uses a lot; menu actions cover the long tail.

## User-Facing Description
```
User: "Rigel, close all tabs."
→ no named app, no Chrome/VS Code keyword match → target = frontmost app
→ discover its menu, fuzzy-match "close all tabs" → e.g. Window > Close All
→ approval card: "chrome: Window > Close All" (or whichever app was frontmost)
```
```
User: "Rigel, what apps are open?"
→ direct reply (no approval gate — it's a query, not an action), plus the
  same list shown in the orb window
```

## Technical Implementation

### New module: `sidecar/handlers/menu_actions.py`
Not an `AppHandler` subclass — a set of functions `brain.py`'s fallback
step and `executor.py`'s new action call directly:

- `frontmost_app() -> str | None` — `osascript`: `tell application "System
  Events" to name of first process whose frontmost is true`
- `list_running_apps() -> list[str]` — `osascript`: `tell application
  "System Events" to get name of every process whose background only is
  false` (Slice 2)
- `discover_menu(app_name: str) -> list[list[str]]` — recursive AX walk
  (`get every menu item of every menu of menu bar 1`, descending into
  submenus), returns menu paths like `["File", "Export", "PDF"]`
- `fuzzy_match(phrase: str, menu_paths: list[list[str]]) -> tuple[list[str], float] | None`
  — best path + confidence, stdlib `difflib.SequenceMatcher` (matches this
  repo's no-casual-new-deps convention rather than pulling in rapidfuzz)
- `is_dangerous(menu_path: list[str]) -> bool` — hard keyword block:
  delete, erase, empty trash, format, quit, uninstall, remove, discard,
  reset, ... — checked against every path segment
- `click_menu_item(app_name: str, menu_path: list[str]) -> tuple[str, str]`
  — `osascript`: `click menu item "<leaf>" of menu "<parent>" of ... of
  menu bar 1`, same `(status, detail)` contract as every other executor
  path

### `brain.py`
New fallback step, engaged only when a target app can actually be
resolved (named in text, or a frontmost app exists) — never on plain
conversation, so it can't misfire on unrelated chat:
```python
def _menu_action_command(text, llm_config) -> list[dict]:
    if registry.match(text) is not None:
        return []  # a named handler owns this utterance; don't also guess a menu click
    app = _resolve_target_app(text) or menu_actions.frontmost_app()
    if app is None:
        return []
    menu = menu_actions.discover_menu(app)
    match = menu_actions.fuzzy_match(text, menu)
    if match is None:
        return []
    path, confidence = match
    return [{"action": "click_menu_item", "args": {"app": app, "menu_path": path}}]
```
Called after `_app_commands()` in `respond()`, same additive pattern.

### `executor.py`
A new action, `click_menu_item` — distinct from `app_action` (the source
note's own tech-debt note is right: this needs `(app, menu_path)`, not a
single flat target string):
- `preview()`: validate `app`/`menu_path` are non-empty; no other
  resolution needed (the path was already validated against a live
  discovery when `brain.py` built it)
- `is_whitelisted()`: consult `menu_actions.is_dangerous(menu_path)`
  *first* — if true, return `False` unconditionally, even if the whitelist
  says `all: true` for this app. This is a new precedent (whitelist can be
  overridden), worth flagging clearly in the whitelist UI copy.
- `execute()`: dispatch to `menu_actions.click_menu_item(app, menu_path)`

### `app.py` / frontend
- `GET /api/rigel/running-apps` (Slice 2)
- `whitelist_config.click_menu_item` — same per-app-id shape as
  `app_action`'s whitelist entry
- Orb window: a visible open-apps list (Slice 2)
- `CommandApproval.jsx`: readable card text for `click_menu_item`, e.g.
  `"chrome: File > Close All Tabs"`

### Slices (from the source note, mapped to concrete deliverables)
1. **Read-only menu discovery** — `discover_menu()` alone, exercised
   standalone (console/script), not wired into chat. Proves the
   Accessibility permission + AX tree walk work at all.
2. **Visible app list** — `list_running_apps()` + `/running-apps` + orb
   window UI + a direct (non-approval-gated) "what apps are open" reply
   path in `brain.py`. Independent of menu execution; can ship first.
3. **Fuzzy match, still read-only** — `fuzzy_match()` wired into the
   `brain.py` fallback so a reply says what it *would* click, without
   calling `click_menu_item`.
4. **Real execution** — `click_menu_item` through `executor.py`'s
   preview/whitelist/execute/log pipeline for real.
5. **Safety pass** — `is_dangerous()` hard-block list, tested against
   Slice 4, before enabling by default.

## Configuration
`whitelist_config` gains `click_menu_item: {app_id: {"all": bool, "menu_paths": [[str, ...], ...]}}`
— a dangerous-item match still forces approval regardless of this.

## Dependencies
- macOS **Accessibility** permission grant (System Settings → Privacy &
  Security → Accessibility) — a new permission surface; `open_app`/
  `close_app`/the existing handlers don't need it. Needs a setup-doc
  callout (`docs/setup/`) before Slice 1 ships to anyone but a developer.
- Builds on: `sidecar/handlers/` (`registry`, `window_ops`) and the
  whitelist/approval pipeline from the merged execution-layer work.

## Open Questions (carried from the source note, unresolved)
1. Should Rigel visibly switch focus to a non-frontmost target app before
   clicking its menu, or only ever act on whatever's already in front?
   Doesn't block Slice 1 (read-only).
2. Submenu fuzzy-match depth/ambiguity: how deep to search, what to do on
   a near-tie between two labels? Proposed default: search 2 levels deep;
   on a near-tie, surface both candidates in the approval card rather than
   guessing. Relevant starting Slice 3.

## Known Limitations
- macOS only, and now requires an additional permission grant beyond what
  `open_app`/`close_app`/the existing handlers need.
- Fuzzy matching is heuristic — mismatches are possible, which is exactly
  why dangerous-sounding items get a hard block independent of whitelist
  state.

## Testing
- **Manual Testing Checklist** (macOS only, mirrors
  `expanded-app-control.md`'s style):
  - [ ] `discover_menu()` returns real menu paths for a running app after
        the Accessibility permission is granted (and a clear error before
        it's granted, not a silent empty list)
  - [ ] `frontmost_app()`/`list_running_apps()` match what's actually open
  - [ ] `fuzzy_match()` picks a sensible item for an unambiguous phrase and
        returns `None` (not a bad guess) for a phrase matching nothing
  - [ ] The `registry.match()` short-circuit works: a Chrome-keyword
        utterance never falls through to a menu-click guess
  - [ ] `executor.is_whitelisted()` forces approval for a dangerous-item
        match even with `all: true` whitelisted for that app
  - [ ] `CommandApproval.jsx` renders a readable `click_menu_item` card

## Future Enhancements
- LLM-assisted disambiguation when `fuzzy_match()` finds a near-tie,
  instead of always surfacing both candidates
- Extend beyond menu bar to other AX-exposed UI (toolbar buttons, etc.) —
  explicitly out of scope for this doc

## Related Features
- `docs/proposals/expanded-app-control.md` — the `AppHandler` framework
  this builds a fallback tier underneath

## References
- Source note: "Rigel Execution Layer — App Menu Actions" (scoping
  interview, 2026-09-19)
- `sidecar/handlers/base.py`, `registry.py`, `window_ops.py`
- `sidecar/brain.py`, `executor.py`, `app.py`
