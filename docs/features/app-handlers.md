# Feature: App Handlers (Per-App Sub-Agents)

## Overview
Rigel can already open and close apps and create/delete files, through a
shared four-verb pass in `sidecar/brain.py` and the approval-gated
execution layer in `sidecar/executor.py`. App Handlers add a second layer
on top: once an app is open, Rigel can carry out *that app's own*
vocabulary — a new Chrome tab, a specific folder opened in VS Code — not
just launch/quit it. Each app gets its own `AppHandler`: a small,
self-contained system prompt plus a Claude tool-use schema describing
exactly what that app supports, dispatched by a router
(`sidecar/handlers/registry.py`) and reporting back through the exact same
approval/whitelist/execution pipeline every other Rigel command uses. It's
Rigel's analogue of how Claude Code itself delegates a scoped task to a
subagent instead of doing everything in one shared context — see the
Architecture section below.

## Status
- [ ] Incubating
- [ ] Planned
- [x] In Development
- [ ] Alpha/Beta
- [ ] Production

The framework itself — registry matching, the approval/whitelist pipeline,
the `GET /handlers` endpoint, the Settings UI — has been exercised via
mocked/smoke tests, but not on macOS. The actual AppleScript and `code` CLI
calls the two concrete handlers make have not yet been run against a real
Chrome or VS Code. See Testing below.

## User-Facing Description
A user can already ask Rigel to open or close an app, approved once or
auto-run per the whitelist configured in Settings. App Handlers add a
second layer for two apps so far:

> **User:** "Rigel, open a new Chrome tab to github.com."
> **User:** "Open ~/projects/rigel in VS Code."

These still go through the same approval card and whitelist a user already
configures in Settings — an app handler's actions are a *new* whitelist
category (per app, not per generic action), not a bypass of the approval
gate. Settings' whitelist screen (`WhitelistSettings.jsx`) grows a new
section per registered handler, listing that app's specific actions
(`new_tab`, `open_folder`, ...) as individually checkable auto-approve
entries, alongside an "Allow all" toggle for the whole app.

If a user asks for something a handler doesn't cover — "open Chrome" with
no in-app action attached — the handler itself is instructed to call
nothing, so the request falls through to the existing generic `open_app`
path instead of being swallowed.

## Technical Implementation

### Architecture — the `AppHandler` sub-agent pattern
Each app Rigel can operate on beyond generic open/close gets its own
`AppHandler`: a system prompt giving an LLM that app's persona, and a
Claude tool-use `tools` schema listing exactly the actions that app
supports. `brain.py`'s existing four-verb pass (open/close app,
create/delete file) is unchanged; on top of it, `brain.py` separately
checks whether the user's text matches a registered handler
(`sidecar/handlers/registry.py`) and, if so, makes that handler's own
scoped Claude tool-use call. A resulting tool call becomes a single new
command type, `app_action`, which flows through the *same*
preview → whitelist-check → approve/auto-run → execute → log pipeline as
every other command — `executor.py` just gained one more action to
recognize, not a parallel pipeline.

```
User prompt → brain.py
                ├─ shared four-verb pass (open/close app, create/delete file)
                └─ registry.match(text) → matched handler's own scoped
                   Claude tool-use call → zero or one `app_action` command
                                │
                                ▼
             executor.py: preview (validates app_id/tool against the
             handler's declared tools) → whitelist check (per app_id, not
             per generic action) → execute (dispatches to the handler's own
             execute_tool, e.g. AppleScript or a CLI) → db.py command log
```

This mirrors, deliberately, how Claude Code itself delegates work to
subagents for a scoped task rather than doing everything in one shared
context — each `AppHandler` is Rigel's analogue: a small, self-contained
sub-agent for one app's vocabulary, dispatched by a router (`brain.py`)
and reporting back through the same approval/logging path everything else
uses. `docs/proposals/expanded-app-control.md`'s Architecture section
makes this comparison explicitly, and it's the framing to keep in mind
reading the rest of this doc: a handler is not a bigger if/else branch in
`executor.py`, it's a peer of Rigel's own brain, scoped to one app.

### Key Components
- **Framework:** `sidecar/handlers/base.py` (the `AppHandler` ABC —
  `app_id`, `display_name`, `match_keywords`, `system_prompt`, `tools`,
  and the abstract `execute_tool`), `sidecar/handlers/registry.py`
  (`register()`/`get()`/`all_handlers()`/`match()`),
  `sidecar/handlers/window_ops.py` (shared `focus`/`minimize`/`is_running`
  AppleScript helpers every handler can reuse instead of reimplementing
  "bring this app's window to the front")
- **Router:** `sidecar/brain.py` — `_app_commands()` calls
  `registry.match(text)` and, on a hit, `llm_providers.claude_app_action()`
- **LLM call:** `sidecar/llm_providers.py` — `claude_app_action()`, which
  uses real Claude tool-use (`tools=handler.tools`) rather than the shared
  four-verb `RESPONSE_SCHEMA` JSON-schema trick, since each handler's tool
  list varies and a single shared schema can't describe all of them
- **Execution:** `sidecar/executor.py` — the `app_action` branch in
  `preview()`/`is_whitelisted()`/`_execute_macos()`, dispatching to
  `handler.execute_tool()`
- **API:** `sidecar/app.py` — `GET /api/rigel/handlers` (lists registered
  handlers + tools for the Settings UI), `AppActionWhitelist` /
  `WhitelistConfig.app_action` (per-app-id whitelist entries)
- **Frontend:** `desktop/src/components/CommandApproval.jsx` (readable
  `app_action` card text), `desktop/src/components/WhitelistSettings.jsx`
  (per-app whitelist section, fed by `getHandlers()` in
  `desktop/src/api.js`)
- **Concrete handlers:** `sidecar/handlers/chrome.py` (`new_tab`,
  `close_tab`, `list_tabs`, `new_window`, `focus`, `minimize`),
  `sidecar/handlers/vscode.py` (`open_file`, `open_folder`, `new_window`,
  `focus`, `minimize`) — the first two proofs of the pattern

### Data Flow
1. User asks for an app-specific action (e.g. "new tab in Chrome to
   github.com").
2. `brain.py`'s shared four-verb pass finds no open/close/file command;
   separately, `registry.match()` finds the Chrome handler by keyword
   (`"chrome"` is one of `ChromeHandler.match_keywords`).
3. `llm_providers.claude_app_action()` asks Chrome's own scoped Claude call
   (`system=handler.system_prompt`, `tools=handler.tools`), which returns
   a `new_tab` tool-use block with `{"url": "github.com"}`.
4. `brain.py` wraps that into `{"action": "app_action", "args": {"app_id":
   "chrome", "tool": "new_tab", "tool_args": {"url": "github.com"}}}` and
   adds it to whatever commands the shared pass already produced.
5. `app.py`'s `/chat` handler calls `executor.preview("app_action", args)`,
   which validates `tool` is one of `ChromeHandler.tools`' names.
6. `executor.is_whitelisted()` checks
   `whitelist["app_action"]["chrome"]` — its own tools list, not the four
   fixed action keys.
7. If not whitelisted, an approval card renders ("chrome: new tab
   (github.com)"); on approval, `executor.execute()` dispatches to
   `ChromeHandler.execute_tool("new_tab", {"url": "github.com"})`, which
   shells out to `osascript`.
8. Result is logged to `command_attempts`, same as any other command.

## Configuration
No new environment variables. `whitelist_config` (the sidecar's persisted
`settings` row) gained one key:
`app_action: {app_id: {"all": bool, "tools": [str, ...]}}`, independent of
the four existing per-action keys (`open_app`, `close_app`, `create_file`,
`delete_file`).

## Usage Examples

### User Perspective
```
User prompt: "Rigel, open a new Chrome tab to github.com."
Rigel response: "Understood. I've logged that and I'm waiting on your
approval to chrome: new tab (github.com) — check the console."
```

### Developer Perspective
```python
# sidecar/handlers/chrome.py — the pattern every handler follows
class ChromeHandler(AppHandler):
    app_id = "chrome"
    display_name = "Google Chrome"
    match_keywords = ["chrome", "google chrome"]
    system_prompt = (
        "You control Google Chrome for Rigel, a voice-activated desktop "
        "agent. ... If the request doesn't clearly match any of your "
        "tools, also call nothing rather than guessing."
    )
    tools = [
        {
            "name": "new_tab",
            "description": (
                "Open a new tab in Chrome's frontmost window (launching "
                "Chrome and/or opening a window first if none exists), "
                "optionally navigating it to a URL."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "..."}},
                "required": [],
            },
        },
        # ... close_tab, list_tabs, new_window, focus, minimize
    ]

    def execute_tool(self, tool_name: str, tool_input: dict) -> tuple[str, str]:
        if tool_name == "new_tab":
            return self._new_tab(tool_input.get("url"))
        # ...
        return ("error", f"'{tool_name}' is not a recognized Chrome action.")


registry.register(ChromeHandler())
```
Any new handler follows the same four steps: subclass `AppHandler`, define
`app_id`/`display_name`/`match_keywords`/`system_prompt`/`tools`,
implement `execute_tool` returning `(status, detail)` and never raising,
and call `registry.register(YourHandler())` at module import time.
`sidecar/handlers/__init__.py` importing every handler module is what
actually populates the registry at process start.

## Testing
- **Unit Tests:** none in this repo yet (matches the project's existing
  "no automated test suite" state, noted in `llm-brain.md`'s architecture
  doc) — verification here was manual/smoke, not an automated suite.
- **Manual Testing Checklist:**
  - [x] `registry.match()` routes "chrome"/"vs code" text to the correct
        handler, including the longest-keyword-wins tie-break — exercised
        via a scratch venv with the two handler modules imported directly.
  - [x] `executor.preview()` rejects an `app_action` whose `tool` isn't in
        the matched handler's declared `tools` list.
  - [x] Per-app whitelist (`whitelist["app_action"]["chrome"]`) auto-runs
        only that app's actions, and a `tools: [...]` entry (not `all`)
        only covers the listed tool names.
  - [x] `GET /api/rigel/handlers` lists both handlers with their
        `name`/`description` per tool.
  - [x] `WhitelistSettings.jsx` renders a working per-app section fed by
        `getHandlers()`, including toggling "Allow all" vs. individual
        tool checkboxes — verified building the frontend cleanly against
        the new component code.
  - [x] `CommandApproval.jsx` shows a readable card for an `app_action`
        (`"chrome: new tab (github.com)"` style).
  - [ ] Chrome handler: `new_tab`/`close_tab`/`list_tabs`/`new_window`/
        `focus`/`minimize` each actually work against a real, running
        Chrome. **Not yet run** — this development environment has no
        macOS to run `osascript` against.
  - [ ] VS Code handler: `open_file`/`open_folder`/`new_window`/`focus`/
        `minimize` each actually work against a real, running VS Code, and
        a missing `code` CLI is handled with the clear error message
        rather than a traceback. **Not yet run**, same reason.
  - [ ] A handler's scoped Claude call, against the real Anthropic API (not
        mocked), correctly returns zero commands for text that isn't
        actually an in-app action (e.g. "open Chrome" alone should stay
        the generic `open_app`, never an `app_action`). **Not yet run.**

The framework's mechanics (registry matching, `preview`/`is_whitelisted`
validation, the whitelist config shape, the `/handlers` endpoint, and the
frontend build) were verified with mocked/smoke tests in a scratch venv —
real checks, but not on macOS and not against a live Chrome, VS Code, or
the real Anthropic API. Every item above that touches an actual
`osascript` call, the `code` CLI, or a live Claude tool-use request is
unconfirmed on real hardware as of this writing. Contrast this with the
separate, later Menu Actions feature (`docs/features/menu-actions.md`),
several slices of which *were* live-tested on a real Mac — this feature's
concrete handler actions haven't had that pass yet.

## Known Limitations
- **macOS only**, same as the rest of the execution layer — `executor.py`'s
  `execute()` returns an `"error"` status immediately on any
  `sys.platform != "darwin"`, and both handlers shell out to `osascript`
  (Chrome, `window_ops`) or a CLI that assumes a Mac install layout (VS
  Code's `code`).
- **Claude-only for now.** `claude_app_action()` uses real Claude tool-use;
  the Ollama path's JSON-mode prompting (`ollama_respond()`) has no
  equivalent yet, so a user on the Ollama provider gets no `app_action`
  commands at all — noted directly in `_app_commands()`'s own docstring in
  `sidecar/brain.py` as a documented future gap, not an oversight.
- **Only two handlers exist so far** (Chrome, VS Code) — every other app
  still only gets the generic open/close/file-CRUD treatment.
- **`registry.match()` is a simple keyword substring match**, not an LLM
  call — an utterance that doesn't mention a known app's keyword
  (`"chrome"`, `"vs code"`, `"vscode"`, `"visual studio code"`) never
  reaches that app's handler, even when it's conversationally obvious
  which app is meant.
- **VS Code's System Events process name is an unconfirmed judgment
  call.** `window_ops.focus`/`minimize` need the exact process name
  System Events sees, and `vscode.py` uses the hardcoded constant
  `"Code"` (the executable name inside
  `Visual Studio Code.app/Contents/MacOS`), not the `"Visual Studio Code"`
  display name — reasoned from how macOS names processes generally, but
  not yet confirmed against a real running VS Code. See the
  troubleshooting doc for how to verify and fix it if wrong.
- **Requires the `code` CLI on `PATH`** for every VS Code action except
  `focus`/`minimize` — see the troubleshooting doc for the exact fix.
- **No execution-layer verification on real hardware yet** for either
  handler — see Testing above.

## Future Enhancements
- More handlers (Finder, Terminal, Slack, ...).
- A generic window-ops handler for apps that only need focus/minimize and
  don't warrant a full custom tool set.
- Route `registry.match()` ambiguity or misses through the LLM instead of
  keyword substring matching.
- Ollama support for `_app_commands()`.
- A dynamic, menu-bar-clicking fallback tier underneath the handlers here,
  for apps nobody's written a handler for — see
  [`docs/features/menu-actions.md`](menu-actions.md), a separate feature
  built specifically because a fixed `tools` list can't express "whatever
  this app's menu bar currently contains" (see the architecture doc's
  "Alternative Approaches Considered" for why that's a different feature
  rather than another `AppHandler`).

## Related Features
- Approval-gated execution layer for open/close app + file CRUD
  (`sidecar/executor.py`).
- Per-action/target whitelist (`desktop/src/components/WhitelistSettings.jsx`).
- Pluggable LLM brain (`docs/features/llm-brain.md`) — `claude_app_action()`
  reuses the same `anthropic.Anthropic()` client and credential resolution
  as `claude_respond()`.
- [`docs/features/menu-actions.md`](menu-actions.md) — the dynamic,
  menu-bar-clicking fallback tier that sits underneath the fixed handlers
  documented here.

## References
- [`docs/architecture/app-handlers.md`](../architecture/app-handlers.md)
- [`docs/api/handler-endpoints.md`](../api/handler-endpoints.md)
- [`docs/troubleshooting/app-handlers.md`](../troubleshooting/app-handlers.md)
- `docs/proposals/expanded-app-control.md` — the original design proposal,
  including the "AppHandler sub-agent" framing this doc builds on
- `sidecar/handlers/base.py`, `registry.py`, `window_ops.py`
- `sidecar/handlers/chrome.py`, `vscode.py`
- `sidecar/brain.py`, `llm_providers.py`, `executor.py`, `app.py`
- `desktop/src/components/CommandApproval.jsx`, `WhitelistSettings.jsx`,
  `desktop/src/api.js`
