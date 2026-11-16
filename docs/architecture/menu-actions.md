# Architecture: App Menu Actions

## Purpose
Lets Rigel act on **any running app's real menu bar** — discovered live via
macOS's Accessibility API, matched against a spoken phrase, and clicked for
real — as a generic fallback beneath the fixed four-verb command set and
the per-app `AppHandler` framework (`sidecar/handlers/`, see
[`docs/architecture/app-handlers.md`](app-handlers.md)). It also exposes a
plain read of what's currently running, independent of any click.

## High-Level Diagram
```
┌──────────────────────┐        ┌─────────────────────────┐
│  RunningApps.jsx (▤)  │        │  Chat box                │
│  GET /running-apps    │        │  POST /chat               │
└──────────┬────────────┘        └──────────┬────────────────┘
           │                                 ▼
           │                      brain.py: respond(text, llm_config)
           │                        1. _running_apps_reply()   ──┐
           │                        2. provider / stub           │ deterministic,
           │                        3. _app_commands() (Chrome/  │ no LLM, no
           │                           VS Code AppHandler)       │ command produced
           │                        4. if still no commands:     │
           │                           _menu_action_commands()  ◀┘
           │                                 │
           ▼                                 ▼
  menu_actions.list_running_apps() ◀── shared with _resolve_target_app()
                                              │
                                 menu_actions.discover_menu(app)
                                              │
                                 menu_actions.fuzzy_match(text, menu)
                                              │
                        1 confident match ────┼──── tie / no match
                              │                            │
                              ▼                            ▼
                {"action": "click_menu_item", ...}   note appended to reply,
                              │                        no command
                              ▼
                  executor.preview() → is_whitelisted() → execute()
                              │            (menu_actions.is_dangerous()
                              │             checked first, forces approval)
                              ▼
                  menu_actions.click_menu_item(app, menu_path)
                              │
                              ▼
                     osascript: click menu item ... of menu bar 1
```

## Components

### `sidecar/handlers/menu_actions.py` (new)
- **Language:** Python
- **Location:** `sidecar/handlers/menu_actions.py`
- **Purpose:** All macOS Accessibility/AppleScript interaction for this
  feature — discovery, matching, danger-checking, and clicking. Not an
  `AppHandler` subclass (see "Fallback tier vs. another `AppHandler`"
  below) and, deliberately, not imported by `sidecar/handlers/__init__.py`'s
  registry — it's called directly by `brain.py` and `executor.py`.
- **Key Files:** single file — small enough not to split.
- **Dependencies:** stdlib only (`subprocess` to shell out to `osascript`,
  `re` for tokenizing in `fuzzy_match()`) — no new third-party dependency,
  matching this repo's existing convention (see `llm-provider-selection.md`
  for the same reasoning applied to Ollama's HTTP client).
- **Public Interface:**
  - `frontmost_app() -> str | None` — raises `MenuDiscoveryError` on
    failure, returns `None` only when there's genuinely no frontmost app.
  - `list_running_apps() -> list[str]` — same error contract.
  - `discover_menu(app_name: str) -> list[list[str]]` — same error
    contract; never returns an empty list to mean "failed."
  - `fuzzy_match(phrase, menu_paths) -> list[tuple[list[str], float]]` —
    pure function, no I/O.
  - `is_dangerous(menu_path: list[str]) -> bool` — pure function.
  - `click_menu_item(app_name, menu_path) -> tuple[str, str]` — **never
    raises** (see "Two error-handling contracts, deliberately" below).
- **Two error-handling contracts, deliberately.** Per the module's own
  docstring: `frontmost_app()`, `list_running_apps()`, and
  `discover_menu()` all *raise* `MenuDiscoveryError`, because they're
  called from `brain.py`'s command-detection phase — before anything is
  logged or approved, where an exception is the natural way to say "this
  attempt produced nothing usable." `click_menu_item()` is the one
  exception: it's called from `executor.execute()`, alongside every other
  action's execution path, which follows a strict
  `(status, detail)`-tuple, never-raises contract so callers never have to
  guess what might go wrong. It even catches its own call to
  `_run_osascript()` (which *can* raise, for "no `osascript` on this
  machine at all") and converts that into an `("error", ...)` tuple rather
  than letting it propagate — the only function in the module that does
  this translation itself.

### `sidecar/brain.py` (modified)
- **Purpose:** Two additions, both deterministic (no LLM call in either
  path):
  - `_running_apps_reply(text)` — matched by `_RUNNING_APPS_QUERY`, checked
    before any provider dispatch. A pure read; never produces a command.
  - `_menu_action_commands(text)` — the fallback tier itself. Gated first
    by `_MENU_ACTION_VERB_HINT` (a cheap regex), then
    `_resolve_target_app(text)` (checks whether any currently-running
    app's name appears in the text, longest name wins on multiple matches)
    or `menu_actions.frontmost_app()` if none is named. Only invoked from
    `respond()` when the shared four-verb pass *and* the `AppHandler` pass
    both produced zero commands — see "Additive, not exclusive" in Data
    Flow below.

### `sidecar/executor.py` (modified)
- **Purpose:** Adds `click_menu_item` as a sixth action alongside the
  original four and `app_action`, through the same
  `preview()`/`is_whitelisted()`/`execute()` contract every other action
  uses.
- `preview()` validates `app` is non-empty and `menu_path` is a non-empty
  list of non-empty strings — no further resolution, since the path was
  already validated against a live `discover_menu()` walk when `brain.py`
  built the command.
- `is_whitelisted()` is where the one-time-only override lives — see
  "The one whitelist override" below.
- `_execute_macos()` dispatches straight to
  `menu_actions.click_menu_item(args["app"], args["menu_path"])`.

### `sidecar/app.py` (modified)
- **Purpose:** `GET /api/rigel/running-apps` (thin wrapper over
  `menu_actions.list_running_apps()`, 503 on `MenuDiscoveryError`) and the
  `MenuActionWhitelist`/`WhitelistConfig.click_menu_item` Pydantic models
  backing `GET`/`POST /api/rigel/settings/whitelist-config`. See
  [`docs/api/menu-actions-endpoints.md`](../api/menu-actions-endpoints.md).

### `desktop/src/components/RunningApps.jsx` / `CommandApproval.jsx` (new/modified)
- **Purpose:** `RunningApps.jsx` is a header dropdown, fetched fresh on
  each open (not polled) — a glance, not a live monitor.
  `CommandApproval.jsx`'s `describe()` gained a `click_menu_item` branch
  rendering `"AppName: Menu > Item"` from `cmd.args.app`/`menu_path`.

## Data Flow

### Primary Flow: a spoken action with no dedicated handler
1. `respond()` runs the shared four-verb pass and the `AppHandler` pass
   (`_app_commands()`) first, exactly as before this feature existed.
2. **Only if both produced zero commands** does `_menu_action_commands()`
   run at all — this is deliberately additive-last, not a parallel
   candidate that could out-compete a more specific match. A Chrome
   keyword utterance that `registry.match()` already handles never reaches
   this fallback.
3. `_MENU_ACTION_VERB_HINT.search(text)` gates the whole path — see
   "The verb-hint pre-filter" below for why this exists as its own step.
4. Target app resolution: `_resolve_target_app(text)` checks the text
   against every currently-running app's name (via
   `menu_actions.list_running_apps()`); if none matches, falls back to
   `menu_actions.frontmost_app()`. Either can raise/return `None`, in
   which case the whole fallback quietly produces nothing.
5. `menu_actions.discover_menu(app)` — the real AppleScript round trip —
   then `menu_actions.fuzzy_match(text, menu)`.
6. Exactly one confident match → a real `click_menu_item` command, appended
   to `commands`. A tie or no match → no command, but an informational
   note is appended to the reply text so the user knows *why* nothing
   happened, rather than Rigel going silent on the request.
7. The command (if any) flows through `app.py`'s normal
   log→preview→whitelist-check→(approve or auto-execute) pipeline —
   nothing about this feature bypasses that.

### Secondary Flow: "what apps are open?"
```
1. _RUNNING_APPS_QUERY matches text
2. menu_actions.list_running_apps() — no Accessibility grant needed
3. Reply built directly from the list; respond() returns immediately,
   before any provider call or command-detection pass runs
```

### Error Handling
- `brain.py`'s two new paths both treat `MenuDiscoveryError` as a soft
  failure: `_running_apps_reply()` turns it into a spoken explanation
  ("I couldn't check what's open: ..."); `_menu_action_commands()` and
  `_resolve_target_app()` both swallow it and just produce no command/no
  match, since this fallback is best-effort on top of an already-complete
  reply, not something explicitly asked for.
- `executor.py`'s `click_menu_item` path never raises past `execute()` —
  a stale menu path (app quit, menu changed between discovery and
  approval) surfaces as an ordinary `("error", ...)` execution result,
  same as a failed `open_app`.

## Concurrency & State Management
No new concurrency concerns — `/chat` and `/running-apps` are both
synchronous FastAPI handlers, same as the rest of the sidecar. Each
`click_menu_item` command discovers its menu fresh at fuzzy-match time
(inside a single `respond()` call) and clicks against a path built from
that same discovery — there's a real window between discovery and a user
clicking Approve where the target app's menu could change, which is an
accepted, documented gap (see `click_menu_item()`'s own docstring: "does
not re-verify the path still exists before clicking").

## Performance Characteristics
- `discover_menu()` is the expensive call in this feature — a real
  AppleScript round trip walking a live app's Accessibility tree.
  Confirmed live against iTerm2: **467 menu items**, including nested
  submenus. This is the direct motivation for the verb-hint pre-filter
  (below) — every plain-conversation turn that reaches `respond()` without
  it would pay this cost for nothing.
- `list_running_apps()`/`frontmost_app()` are cheap by comparison — a
  single flat System Events query, no per-app tree walk, and confirmed
  live to need no Accessibility grant at all (only walking a *specific*
  app's UI elements does).
- `fuzzy_match()` and `is_dangerous()` are both pure, in-memory, and
  effectively free relative to the AppleScript calls around them.

## External Dependencies
| Dependency | Version | Purpose | License |
|-----------|---------|---------|---------|
| `osascript` (macOS system binary) | OS-provided | Accessibility API access via AppleScript/System Events | Apple (system component, not a project dependency) |

No new Python or JS packages — this feature is stdlib-only on the backend
(`subprocess`, `re`), matching the repo's existing "no casual new deps"
convention.

## Alternative Approaches Considered

- **Fuzzy-matching algorithm — tried three ways, in sequence, each caught
  by testing before it shipped:**
  1. **Full-string `difflib.SequenceMatcher.ratio()` (rejected).** Scored
     each candidate by whole-string character similarity between the
     phrase and the menu label. This degrades badly the moment the phrase
     includes words the label doesn't have — which is the *common* case,
     not an edge case: "copy this in TextEdit" scored *below* the match
     threshold against "Edit > Copy," because "in textedit" dilutes the
     whole-string ratio against a two-word label.
  2. **Character-based "partial ratio" (rejected).** Fixed the dilution
     problem by scoring the best-matching same-length character window
     instead of the whole string, but introduced a worse failure mode:
     spurious character coincidence across unrelated words. Verified
     live/by test: "minimize the textedit window" ranked "Edit > Copy"
     *above* "Window > Minimize," purely because enough characters lined
     up by accident, not because the words had anything to do with each
     other.
  3. **Word-token overlap (adopted).** Scores each candidate by what
     fraction of the candidate's own distinctive words (stopwords
     excluded) appear in the phrase — `fuzzy_match()`'s actual
     implementation. This asks the right question ("how many of this
     menu item's own words did the user actually say") instead of a
     character-coincidence proxy for it, and was verified correct on
     every case that broke the first two approaches, including the
     ambiguous-tie case. The module's own docstring documents why the
     simpler approaches were rejected, right next to the working one.

- **Generic fallback tier vs. another `AppHandler` (adopted: fallback
  tier).** An `AppHandler` subclass (`chrome.py`, `vscode.py`) declares a
  *fixed* `tools` list at class-definition time — right for a well-known,
  stable vocabulary, wrong for "whatever this app's menu bar currently
  contains," which is dynamic and app-state-dependent (a greyed-out Edit
  menu item, an app-specific submenu that only exists with a document
  open). Menu actions instead get their own module, matched not by
  `registry.match()`'s keyword lookup but by a fallback step in
  `brain.py`: only after the shared four-verb pass *and* the `AppHandler`
  registry both come back empty does Rigel resolve a target app and try
  generic menu discovery + fuzzy match. Named handlers stay the fast,
  precise path for actions with no menu equivalent (Chrome's `list_tabs`
  isn't a menu item); menu actions become the universal safety net for
  everything else, including apps nobody's written a handler for at all
  (Finder, Safari, Slack, ...). See
  [`docs/architecture/app-handlers.md`](app-handlers.md) for the handler
  framework this sits underneath. **Rejected alternative:** make menu
  actions the *only* mechanism and retire Chrome/VS Code's custom tools —
  a live AX tree walk + fuzzy match is slower and less precise than a
  hand-declared tool for an app's common actions, and can't express
  actions with no menu equivalent at all.

- **A cheap verb-hint pre-filter before any AppleScript call (adopted).**
  `_MENU_ACTION_VERB_HINT` is a plain regex checked *before* resolving a
  target app or discovering anything — purely a cost/latency guard, not a
  correctness mechanism (it doesn't need to be precise; `fuzzy_match()`
  still does the real filtering afterward). Justified directly by the
  467-item live iTerm2 measurement above: paying a real AppleScript round
  trip on every single chat turn, including "thanks" and "how's it
  going," would be wasteful and slow for zero benefit, since those turns
  can never fuzzy-match anything meaningful anyway.

- **Overriding the whitelist for dangerous items (adopted, and the one
  such override in the codebase).** `executor.is_whitelisted()` checks
  `menu_actions.is_dangerous(menu_path)` **first**, before consulting the
  whitelist at all, and a match forces `False` — approval required —
  unconditionally, even when that app's whitelist entry is `all: true`.
  Every other whitelistable action (`open_app`, `close_app`,
  `app_action`, ...) trusts a fixed, known-in-advance name or tool
  string — the whitelist author knows exactly what they're
  auto-approving. A dynamically-discovered menu item's label is only
  known at request time, so nothing could have vetted "Empty Trash" or
  "Uninstall" in advance the way a whitelist normally implies. The keyword
  list (`_DANGEROUS_KEYWORDS`) is deliberately over-broad — delete, erase,
  empty trash, format, quit, uninstall, remove, discard, reset, wipe,
  destroy — since a false positive here just costs one extra approval
  click, while a false negative could mean an unattended destructive
  click.

## Future Improvements
- LLM-assisted disambiguation on a fuzzy-match tie, instead of always
  surfacing both candidates in the reply text.
- A "remember this" affordance on the `CommandApproval.jsx` card to
  populate the `click_menu_item` whitelist without a manual API call —
  there's currently no Settings UI section for it at all (see the feature
  doc's Known Limitations).
- Extending discovery beyond the menu bar to other Accessibility-exposed
  UI (toolbar buttons, etc.) — explicitly out of scope for this
  implementation.

## Testing Strategy
- **Unit tests (mocked):** `fuzzy_match()` (confident match, genuine tie,
  no-match), `brain._menu_action_commands()` and `_running_apps_reply()`
  with `menu_actions` mocked out, and `executor.preview()`/
  `is_whitelisted()`/`execute()` for `click_menu_item` — including the
  dangerous-item-overrides-whitelist case and confirming
  `click_menu_item()` never raises even when `osascript` is entirely
  missing. None of this requires macOS, which is why it could all be
  built and verified in this (non-macOS) development environment.
- **Manual, live hardware (macOS):**
  - `discover_menu()` confirmed against a real, running iTerm2: 467 menu
    items, including nested submenus to the intended depth (e.g.
    `Apple > Recent Items > Applications`).
  - `frontmost_app()`/`list_running_apps()` confirmed to need no
    Accessibility grant, and to correctly report what was actually
    running/frontmost at the time.
  - The `▤` running-apps dropdown and the "what apps are open?" chat query
    both confirmed working live, end to end through the real UI/API.
  - **Not yet verified live: an actual `click_menu_item()` execution.**
    This is the one function in the module whose live behavior this
    environment genuinely cannot substitute a mock for — everything
    upstream of it (discovery, matching, the whitelist/approval logic) has
    live or unit-test confirmation; the click itself does not yet.

## References
- [`docs/features/menu-actions.md`](../features/menu-actions.md)
- [`docs/api/menu-actions-endpoints.md`](../api/menu-actions-endpoints.md)
- [`docs/troubleshooting/menu-actions.md`](../troubleshooting/menu-actions.md)
- [`docs/architecture/app-handlers.md`](app-handlers.md) — the `AppHandler`
  framework this feature sits underneath as a fallback tier
- [`docs/proposals/menu-actions.md`](../proposals/menu-actions.md) — full
  design record, including the Progress Log this doc's testing claims and
  "Alternative Approaches" section are drawn from
- `sidecar/handlers/menu_actions.py`, `sidecar/brain.py`,
  `sidecar/executor.py`, `sidecar/app.py`
- Apple's AppleScript/System Events "UI element" scripting model (the
  underlying Accessibility API surface `menu_actions.py` scripts against)
