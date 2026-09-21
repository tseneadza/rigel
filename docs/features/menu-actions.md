# Feature: App Menu Actions

## Overview
Rigel's execution layer previously knew only a small fixed verb list
(`open_app`/`close_app`/`create_file`/`delete_file`), plus two apps
(Chrome, VS Code) with their own hand-written command vocabularies via the
`AppHandler` framework. App Menu Actions goes further: Rigel can discover
and click **any running app's real menu-bar items** — dynamically, at
request time, via macOS's Accessibility API — instead of needing someone
to hand-wire one intent per action forever. It also gives Rigel (and the
user) a live view of what's actually running, independent of any menu
click.

## Status
- [ ] Planned
- [ ] In Development
- [x] Alpha/Beta
- [ ] Production

*(Discovery, the running-apps list, and fuzzy matching are all confirmed
working against real hardware. The final step — actually clicking a menu
item — is built and verified via mocked tests only; it has not yet been
run against a real click on a real Mac. See Testing below.)*

## User-Facing Description
Three things fall out of this feature, all through the normal chat box —
no new UI to learn beyond a small header button:

- **"What apps are open?"** answers directly and immediately, with no
  approval step (it's a read, not an action):
  ```
  User: "what apps are open?"
  Rigel: "Open apps: Finder, Google Chrome, iTerm2, Rigel, TextEdit."
  ```
  The same list is available at a glance from the **▤** button in the orb
  window's header — click it for a dropdown of everything currently
  running, fetched fresh each time you open it.
- **A spoken action Rigel doesn't have a dedicated handler for** falls
  through to a live menu-bar search of the app you named (or, if you
  didn't name one, whatever app is currently frontmost):
  ```
  User: "Rigel, close all tabs."
  Rigel: → target = frontmost app (say, Chrome) → discovers its menu bar →
          fuzzy-matches "close all tabs" against Window > Close All →
          approval card: "Google Chrome: Window > Close All"
  ```
  ```
  User: "copy this in TextEdit"
  Rigel: → target = TextEdit (named in the phrase) → Edit > Copy →
          approval card: "TextEdit: Edit > Copy"
  ```
  Like every other command, this shows up as an approval card in the
  console — nothing clicks until you hit **Approve** (unless you've
  explicitly whitelisted it; see Configuration below).
- **An ambiguous phrase gets no guess.** If more than one menu item is a
  near-equally-good match, Rigel doesn't pick one — it says so in its
  reply instead of producing a command:
  ```
  Rigel: "...(That could be a few different menu actions in TextEdit:
  Edit > Copy; or File > Duplicate — not sure which, so I didn't guess.)"
  ```

## Technical Implementation

### Architecture
```
"Rigel, close all tabs"
        │
        ▼
brain.py: respond()
  1. _running_apps_reply()     ─▶ direct answer, no LLM, no command
  2. provider (stub/Claude/Ollama) ─▶ reply + shared four-verb commands
  3. _app_commands()           ─▶ Chrome/VS Code AppHandler match, if any
  4. if still no commands:
     _menu_action_commands()   ─▶ THIS FEATURE
       │
       ├─ _MENU_ACTION_VERB_HINT gate (cheap regex, avoids paying for
       │  an AppleScript round trip on plain chat)
       ├─ _resolve_target_app(text) or menu_actions.frontmost_app()
       ├─ menu_actions.discover_menu(app)   ── AppleScript / Accessibility
       ├─ menu_actions.fuzzy_match(text, menu)
       │    1 confident match  → {"action": "click_menu_item", ...}
       │    tie or no match    → informational note appended to reply, no command
       ▼
executor.py: preview() → is_whitelisted() → execute()
       │                                        │
       │                        menu_actions.is_dangerous() checked FIRST —
       │                        forces approval even if whitelisted "all: true"
       ▼
menu_actions.click_menu_item(app, menu_path)  ── AppleScript click, real execution
```

### Key Components
- **Backend:** `sidecar/handlers/menu_actions.py` (new module —
  `frontmost_app()`, `list_running_apps()`, `discover_menu()`,
  `fuzzy_match()`, `is_dangerous()`, `click_menu_item()`),
  `sidecar/brain.py` (`_RUNNING_APPS_QUERY`, `_running_apps_reply()`,
  `_MENU_ACTION_VERB_HINT`, `_resolve_target_app()`,
  `_menu_action_commands()`, all wired into `respond()`), `sidecar/
  executor.py` (`click_menu_item` branches of `preview()`/
  `is_whitelisted()`/`_execute_macos()`), `sidecar/app.py` (`GET
  /api/rigel/running-apps`, `MenuActionWhitelist`/`WhitelistConfig`).
- **Frontend:** `desktop/src/components/RunningApps.jsx` (the header **▤**
  dropdown), `desktop/src/components/CommandApproval.jsx` (renders a
  `click_menu_item` command as `"AppName: Menu > Item"`), `desktop/
  src/api.js` (`getRunningApps`).
- **Storage:** `whitelist_config.click_menu_item` in the existing
  `settings` key/value table — same table `orb_config`/`llm_config` use,
  no schema migration.
- **APIs:** see
  [`docs/api/menu-actions-endpoints.md`](../api/menu-actions-endpoints.md).

### Data Flow
1. User sends a chat message. `brain.py`'s `respond()` first checks
   `_running_apps_reply()` — if the text matches a "what apps are
   open"-style query, it answers directly from
   `menu_actions.list_running_apps()` and returns immediately, no command,
   no provider call.
2. Otherwise the message goes through the normal provider/stub pass and
   the Chrome/VS Code `AppHandler` pass, same as before this feature
   existed.
3. **Only if neither of those produced any command at all**, `respond()`
   calls `_menu_action_commands(text)`. This checks
   `_MENU_ACTION_VERB_HINT` first (a cheap regex) purely to avoid paying
   for an AppleScript round trip on plain conversation.
4. If the hint matches, it resolves a target app — a running app named in
   the text, else the frontmost app — then calls
   `menu_actions.discover_menu(app)` (a live Accessibility-API walk of
   that app's menu bar) and `menu_actions.fuzzy_match(text, menu)`.
5. A single confident match becomes a real `{"action": "click_menu_item",
   "args": {"app": ..., "menu_path": [...]}}` command, appended to
   whatever commands already exist. It goes through the exact same
   logging/approval pipeline as `open_app` or an `app_action` command —
   nothing here bypasses approval.
6. `executor.preview()` validates `app`/`menu_path` are present and
   well-formed. `executor.is_whitelisted()` checks
   `menu_actions.is_dangerous(menu_path)` first — a match forces manual
   approval unconditionally, even if the user whitelisted `all: true` for
   that app.
7. On approval (or an auto-whitelisted match), `executor.execute()`
   dispatches to `menu_actions.click_menu_item(app, menu_path)`, which
   builds and runs the actual AppleScript click and returns `("ok"|
   "error", detail)`.

## Configuration
No environment variables. The one piece of setup is a one-time macOS
permission grant — **System Settings → Privacy & Security →
Accessibility** — for whatever process runs the sidecar. Without it,
`discover_menu()`/`click_menu_item()` return a clear
`MenuDiscoveryError`/`("error", ...)` rather than silently doing nothing;
see
[`docs/troubleshooting/menu-actions.md`](../troubleshooting/menu-actions.md).

Auto-approval is opt-in via `whitelist_config`:
```json
"click_menu_item": {
  "Google Chrome": { "all": false, "menu_paths": [["Window", "Close All"]] }
}
```
A dangerous-sounding item (see `menu_actions.is_dangerous()`) always
requires approval regardless of this setting — there's no way to
whitelist past it. There's currently no Settings UI section to populate
this whitelist (deliberately deferred — see Known Limitations); it can
only be set by calling the whitelist-config API directly.

## Usage Examples

### User Perspective
```
User prompt: "Rigel, close all tabs."
Rigel response: "Understood. I've logged that and I'm waiting on your
approval to click menu item — check the console. What's next?"
[Console shows an approval card: "Google Chrome: Window > Close All"]
```
```
User prompt: "what apps are open?"
Rigel response: "Open apps: Finder, Google Chrome, iTerm2, Rigel, TextEdit."
```
```
User prompt: "copy this in TextEdit"
Rigel response: "...(nothing to act on from the base pass)... TextEdit:
Edit > Copy" [approval card appears]
```

### Developer Perspective
```python
from sidecar.handlers import menu_actions

# Discover a running app's real menu bar (requires Accessibility grant)
menu = menu_actions.discover_menu("TextEdit")
# [["File", "New"], ["Edit", "Copy"], ["Edit", "Paste"], ...]

# Rank menu paths against a spoken phrase
matches = menu_actions.fuzzy_match("copy this in textedit", menu)
# [(["Edit", "Copy"], 1.0)]

# Click it for real (only ever called from executor.execute(), post-approval)
status, detail = menu_actions.click_menu_item("TextEdit", ["Edit", "Copy"])
# ("ok", "Clicked Edit > Copy in TextEdit.")
```

## Testing
- **Unit Tests:** mocked tests for `fuzzy_match()` (confident match, tie,
  no-match), `brain._menu_action_commands()`, and
  `executor.preview()`/`is_whitelisted()`/`execute()` for
  `click_menu_item` — none of these require macOS.
- **Manual Testing Checklist:**
  - [x] `discover_menu()` returns real menu paths for a running app once
        Accessibility is granted — confirmed live: 467 real menu items
        enumerated for iTerm2, including nested submenus to the intended
        depth.
  - [x] `frontmost_app()`/`list_running_apps()` match what's actually open
        — confirmed live, and confirmed neither needs the Accessibility
        grant that `discover_menu()` does.
  - [x] The `▤` running-apps dropdown shows real running apps — confirmed
        live.
  - [x] "What apps are open?" answers directly in chat instead of falling
        through to the stub — confirmed live.
  - [x] `fuzzy_match()` picks a sensible item for an unambiguous phrase,
        reports a tie rather than guessing on an ambiguous one, and
        returns nothing for a phrase matching no menu item — verified
        with mocked `discover_menu()` output (this dev environment has no
        macOS); not yet tried against a real discovered menu.
  - [x] `executor.is_whitelisted()` forces approval for a dangerous-item
        match even with `all: true` whitelisted for that app — verified.
  - [x] `CommandApproval.jsx` renders a readable `click_menu_item` card —
        verified (frontend build clean).
  - [ ] **An actual `click_menu_item()` execution against a real running
        app on real hardware.** Built and verified via mocked
        `osascript` calls only — this is the one thing this development
        environment genuinely cannot substitute a mock for.

## Known Limitations
- **macOS only**, and it's the first Rigel feature to need the
  Accessibility permission grant specifically (existing actions only need
  the "control this app" AppleScript prompt, not full Accessibility
  access).
- **Fuzzy matching is heuristic.** It's word-token overlap, not semantic
  understanding — an unusual phrasing may find nothing, or may tie between
  two genuinely similar-sounding items, and Rigel refuses to guess in
  either case rather than risk clicking the wrong thing.
- **No Settings UI to pre-populate the `click_menu_item` whitelist.**
  Unlike `app_action` (fed by the fixed, enumerable handler+tool list from
  `GET /handlers`), there's no fixed set of `(app, menu path)` pairs to
  list ahead of time — populating this whitelist needs either manual API
  calls or a future "remember this" affordance on the approval card
  itself.
- **The actual click has not yet been verified on real hardware** — see
  Testing above. Discovery, the running-apps list, and fuzzy matching all
  have live confirmation; the click itself does not yet.
- Rigel never switches focus to a non-frontmost app before acting on it —
  it clicks whatever app was resolved as the target, in the background if
  necessary (this matches how AppleScript `click` works, not a deliberate
  UX choice either way — open question, see the proposal doc).

## Future Enhancements
- LLM-assisted disambiguation when `fuzzy_match()` finds a near-tie,
  instead of always surfacing both candidates in the reply.
- A "remember this" affordance on the approval card to populate the
  `click_menu_item` whitelist without a manual API call.
- Extend beyond the menu bar to other Accessibility-exposed UI (toolbar
  buttons, etc.) — explicitly out of scope for this feature.

## Related Features
- [`docs/features/app-handlers.md`](app-handlers.md) — the `AppHandler`
  framework (Chrome, VS Code) this feature sits underneath as a generic
  fallback for apps with no dedicated handler, or actions a handler
  doesn't cover.

## References
- `sidecar/handlers/menu_actions.py`, `sidecar/brain.py`,
  `sidecar/executor.py`, `sidecar/app.py`
- `desktop/src/components/RunningApps.jsx`,
  `desktop/src/components/CommandApproval.jsx`, `desktop/src/api.js`
- [`docs/architecture/menu-actions.md`](../architecture/menu-actions.md)
- [`docs/api/menu-actions-endpoints.md`](../api/menu-actions-endpoints.md)
- [`docs/troubleshooting/menu-actions.md`](../troubleshooting/menu-actions.md)
- [`docs/proposals/menu-actions.md`](../proposals/menu-actions.md) — the
  full design/progress record this doc set is built from
