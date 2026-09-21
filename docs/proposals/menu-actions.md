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
- [ ] In Development
- [x] Alpha/Beta
- [ ] Incubating
- [ ] Production

*(Maps the source note's `status: ready` onto this repo's vocabulary; now
`Alpha/Beta` — all 5 originally-scoped slices are code-complete as of
Slice 4 (see Progress Log), including the Slice 5 safety pass, folded in
rather than staged separately. What's left is real-hardware verification
of the click itself, not new development. That note lives outside this
repo and can't be written back to from here; update it
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
  list on demand.
- **Slice 2 validated on real hardware.** ▤ dropdown shows real running
  apps; "what apps are open?" answers directly in chat instead of falling
  through to the stub. One snag along the way, not a code bug: the sidecar
  is a plain Python process with no auto-reload, so after `git pull` it
  kept serving pre-Slice-2 code (a 404 on `/running-apps`, the old stub
  reply for the chat query) until manually restarted — worth remembering
  for every future slice too, unlike the Vite frontend dev server, which
  hot-reloads on its own.
- **Slice 3 landed**: `menu_actions.fuzzy_match()` and a read-only note
  layered onto `brain.py`'s reply (`_menu_action_note`) whenever nothing
  else already produced a command for the utterance — never a command
  itself, never executed, just "I'd click X > Y in App" (or, on a genuine
  tie, all tied candidates) appended to whatever reply was already going
  out. Two design decisions made along the way, beyond what this doc
  originally specified:
  - **A verb-hint pre-filter** (`_MENU_ACTION_VERB_HINT`) gates the whole
    path before anything else runs. Resolving a target app and walking its
    menu bar is a real AppleScript round trip (467 items for a real
    iTerm2, per Slice 1's live test) — worth paying only when the phrase
    plausibly names an action, not on every "thanks" or "how's it going."
  - **The matching algorithm changed mid-implementation, caught by
    testing before it shipped.** The first cut scored candidates via
    `difflib.SequenceMatcher.ratio()` over full strings (phrase vs. menu
    label) — this degrades badly once the phrase includes words the label
    doesn't have, which is the common case ("copy this in TextEdit" scored
    *below* the match threshold against "Edit > Copy", because "in
    textedit" dilutes the whole-string ratio). A "partial ratio" variant
    (best character-match window) fixed the dilution but introduced worse
    failures: it ranked "Edit > Copy" *above* "Window > Minimize" for
    "minimize the textedit window," on pure character coincidence.
    Replaced both with **word-token overlap** (what fraction of a menu
    item's own distinctive words, stopwords excluded, appear in the
    phrase) — verified correct on every case that broke the character-based
    approaches, including the ambiguous-tie case. `fuzzy_match()`'s
    docstring reflects the final algorithm; the module docstring notes why
    the simpler approaches were rejected.
  - Fully verified with mocked `discover_menu()`/`list_running_apps()`
    (this environment has no macOS) for: a single confident match, a
    genuine tie (reports both candidates), a no-match phrase (silently
    returns nothing), plain conversation never reaching the AppleScript
    path at all, and an existing command (e.g. `open Chrome`) never
    getting a menu note appended alongside it. Not yet tried against a
    real discovered menu on real hardware.
- **Slice 4 landed**: real execution. `menu_actions.click_menu_item()`
  builds the nested `menu item "X" of menu 1 of ...` AppleScript reference
  matching a path's exact depth and clicks it — the one function in this
  module that follows `executor.py`'s never-raises `(status, detail)`
  contract rather than raising `MenuDiscoveryError`, since it's called
  from `executor.execute()`, after preview/approval, not from `brain.py`'s
  detection phase. `menu_actions.is_dangerous()` is the safety piece: a
  fixed keyword list (delete, erase, empty trash, format, quit, uninstall,
  ..., deliberately over-broad — a false positive here just costs one
  extra approval) checked against a path's full text; `executor.py`'s
  `is_whitelisted()` consults it *before* anything else and forces
  approval unconditionally on a match, even with that app's whitelist
  entry set to `all: true` — the one whitelist override in the whole
  codebase, since a dynamically-discovered menu item's label can't be
  vetted in advance the way a fixed action or tool name can be.
  `sidecar/brain.py`'s `_menu_action_note` became `_menu_action_commands`:
  a single confident fuzzy match now returns a real `click_menu_item`
  command (approval-gated, same pipeline as every other command); a
  genuine tie still returns no command and the same Slice-3-style
  informational note, since nothing should guess between two candidates.
  `whitelist_config` gained `click_menu_item: {app: {all, menu_paths}}`
  (`app.py`), and `CommandApproval.jsx` renders it as `"iTerm2: File > New
  Window"`. **Deliberately out of scope for this slice**: no
  `WhitelistSettings.jsx` section for `click_menu_item` yet — unlike
  `app_action`'s fixed, enumerable handler+tool list (fed by `GET
  /handlers`), there's no fixed set of (app, menu path) pairs to list
  ahead of time; pre-populating this whitelist needs either manual entry
  or a "remember this" affordance on the approval card itself, either of
  which is its own small feature, not implied by "wire click_menu_item
  through the whitelist pipeline."
  Fully verified: `executor.preview()`/`is_whitelisted()`/`execute()` for
  `click_menu_item` (including the dangerous-item-overrides-whitelist
  case, and confirming `click_menu_item()` never raises even when
  `osascript` is entirely missing); the whitelist API round-trips a
  `click_menu_item` entry correctly; `brain.py` produces a real command on
  a confident match and still no command on a tie; every previously-tested
  path (plain chat, `open Chrome`, "what apps are open?") is unaffected;
  frontend builds clean. Not yet tried against a real click on real
  hardware — this is the first slice where something actually executes,
  so that's the one thing this environment genuinely cannot substitute a
  mock for.

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
- `fuzzy_match(phrase: str, menu_paths: list[list[str]]) -> list[tuple[list[str], float]]`
  — ranks by word-token overlap between the phrase and each path's own
  distinctive words, stdlib `re` only (matches this repo's
  no-casual-new-deps convention rather than pulling in rapidfuzz); empty
  list if nothing clears threshold, more than one entry only on a genuine
  near-tie (see Progress Log for why token overlap replaced two
  character-similarity approaches tried first)
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
# Slice 4 sketch — Slice 3's actual _menu_action_note() (landed) only
# appends a read-only reply note, never a command; this is what turning
# that into a real, executable command looks like once Slice 4 starts.
# Reuses Slice 3's _resolve_target_app()/_MENU_ACTION_VERB_HINT as-is.
def _menu_action_command(text, llm_config) -> list[dict]:
    if not _MENU_ACTION_VERB_HINT.search(text):
        return []
    app = _resolve_target_app(text) or menu_actions.frontmost_app()
    if app is None:
        return []
    menu = menu_actions.discover_menu(app)
    matches = menu_actions.fuzzy_match(text, menu)
    if len(matches) != 1:
        return []  # no match, or a genuine tie — Slice 4 shouldn't guess either
    path, confidence = matches[0]
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
   preview/whitelist/execute/log pipeline for real. **Landed** — and folds
   in Slice 5 below: it would have been unsafe to ship real execution
   without the hard-block already in place, so `is_dangerous()` was built
   as part of `is_whitelisted()` from the start rather than staged as a
   separate follow-up.
5. ~~**Safety pass** — `is_dangerous()` hard-block list, tested against
   Slice 4, before enabling by default.~~ Folded into Slice 4 (see above)
   rather than done as a separate pass afterward.

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
