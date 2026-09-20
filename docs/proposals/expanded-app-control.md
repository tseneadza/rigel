# Feature: Expanded App-Operation Control

## Overview
Rigel detects open/close app intents and executes them through an
approval-gated execution layer, with a per-action/target whitelist to skip
approval for trusted commands (`sidecar/executor.py`,
`desktop/src/components/CommandApproval.jsx`,
`desktop/src/components/WhitelistSettings.jsx`). This feature goes further:
giving the user control over *how* Rigel operates the apps it opens — not
just launching/quitting them, but app-specific actions like opening a new
Chrome tab or a specific folder in VS Code — through a per-app "handler"
pattern (`sidecar/handlers/`), each handler acting as its own small,
LLM-backed sub-agent for one app.

This doc originally recorded a verification done alongside the initial
proposal: at the time of writing, `main` (`feda36d`) already contained the
approval-gated execution layer, the whitelist feature, and the close/quit/
kill intent fix from a prior session — confirmed merged and pushed, nothing
outstanding.

## Status
- [ ] Incubating
- [ ] Planned
- [x] In Development
- [ ] Alpha/Beta
- [ ] Production

## User-Facing Description
A user can already ask Rigel to open or close an app, approved once or
auto-run per the whitelist. This feature adds a second layer on top: once an
app is open, its own handler can carry out app-specific requests, e.g.:

> **User:** "Rigel, open a new Chrome tab to github.com." / "Open
> ~/projects/rigel in VS Code."

Still routed through the same approval gate and whitelist users already
configure in Settings — an app handler's actions are a new whitelist
category (per app, not per generic action), not a bypass of the gate.

## Technical Implementation

### Architecture — the "AppHandler" sub-agent pattern
Each app Rigel can operate on gets its own `AppHandler`: a system prompt
giving an LLM that app's persona, plus a Claude tool-use `tools` schema
listing exactly the actions that app supports. `brain.py`'s existing
four-verb pass (open/close app, create/delete file) is unchanged; on top of
it, `brain.py` separately checks whether the user's text matches a
registered handler (`sidecar/handlers/registry.py`) and, if so, makes that
handler's own scoped Claude tool-use call. A resulting tool call becomes a
single new command type, `app_action`, which flows through the *same*
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
uses.

### Key Components
- **Framework:** `sidecar/handlers/base.py` (the `AppHandler` interface),
  `sidecar/handlers/registry.py` (registration + keyword matching),
  `sidecar/handlers/window_ops.py` (shared AppleScript focus/minimize
  helpers)
- **Router:** `sidecar/brain.py` — `_app_commands()` matches text to a
  handler and calls its scoped LLM request
- **LLM call:** `sidecar/llm_providers.py` — `claude_app_action()`, using
  real Claude tool-use (`tools=handler.tools`) rather than the shared
  four-verb JSON-schema trick, since each handler's tool list varies
- **Execution:** `sidecar/executor.py` — `app_action` branch in
  `preview`/`is_whitelisted`/`execute`, dispatching to
  `handler.execute_tool()`
- **API:** `sidecar/app.py` — `GET /api/rigel/handlers` (lists registered
  handlers + tools for the Settings UI), `WhitelistConfig.app_action`
  (per-app-id whitelist entries)
- **Frontend:** `CommandApproval.jsx` (readable `app_action` card text),
  `WhitelistSettings.jsx` (per-app whitelist section, fed by `/handlers`)
- **Concrete handlers:** `sidecar/handlers/chrome.py` (new_tab, close_tab,
  list_tabs, new_window, focus, minimize), `sidecar/handlers/vscode.py`
  (open_file, open_folder, new_window, focus, minimize) — the first two
  proofs of the pattern, built in parallel against the frozen interface
  above

### Data Flow
1. User asks for an app-specific action (e.g. "new tab in Chrome to github.com")
2. `brain.py`'s shared pass finds no open/close/file command; separately,
   `registry.match()` finds the Chrome handler
3. `llm_providers.claude_app_action()` asks Chrome's own scoped Claude call,
   which returns a `new_tab` tool call with `{"url": "github.com"}`
4. `executor.preview()` validates `new_tab` is one of Chrome's declared tools
5. `executor.is_whitelisted()` checks `whitelist["app_action"]["chrome"]`
6. If not whitelisted, an approval card renders ("chrome: new tab
   (github.com)"); on approval, `executor.execute()` dispatches to
   `ChromeHandler.execute_tool("new_tab", {"url": "github.com"})`
7. Result is logged to `command_attempts`, same as any other command

## Configuration
No new environment variables. `whitelist_config` gained one key:
`app_action: {app_id: {"all": bool, "tools": [str, ...]}}`, independent of
the four existing action keys.

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
    system_prompt = "..."
    tools = [{"name": "new_tab", "description": "...", "input_schema": {...}}, ...]

    def execute_tool(self, tool_name, tool_input):
        ...  # AppleScript via subprocess, same (status, detail) contract as executor.py

registry.register(ChromeHandler())
```

## Testing
- **Manual Testing Checklist:**
  - [ ] `registry.match()` routes "chrome"/"vs code" text to the right handler
  - [ ] A handler's scoped Claude call returns zero commands for text that
        isn't actually an in-app action (e.g. "open Chrome" — should stay
        the generic `open_app`, not an `app_action`)
  - [ ] `executor.preview()` rejects a tool name not in the handler's `tools`
  - [ ] Per-app whitelist (`app_action.<app_id>`) auto-runs only that app's
        actions, not another app's
  - [ ] `GET /api/rigel/handlers` lists both handlers with their tools
  - [ ] `WhitelistSettings.jsx` renders a working per-app section
  - [ ] `CommandApproval.jsx` shows a readable card for an `app_action`
  - [ ] Chrome handler: new_tab/close_tab/list_tabs/new_window/focus/minimize
        each work against a real running Chrome
  - [ ] VS Code handler: open_file/open_folder/new_window/focus/minimize
        each work against a real running VS Code, and `code` CLI missing is
        handled with a clear error rather than a traceback

## Known Limitations
- macOS only, same as the rest of the execution layer.
- Handler support is Claude-only for now — `claude_app_action()` uses real
  tool-use, which the Ollama path's JSON-mode prompting doesn't have an
  equivalent for yet.
- Two handlers exist so far (Chrome, VS Code); everything else still only
  gets the generic open/close/file-CRUD treatment.
- `registry.match()` is a simple keyword substring match, not the LLM
  itself — an utterance that doesn't mention a known app's keyword never
  reaches that app's handler, even if it's conversationally clear which app
  is meant.

## Future Enhancements
- More handlers (Finder, Terminal, Slack, ...)
- Generic window ops (focus/minimize) as their own lightweight handler for
  apps that don't need a full custom tool set
- Route `registry.match()` ambiguity (or misses) through the LLM instead of
  keyword matching
- Ollama support for `_app_commands()`

## Related Features
- Approval-gated execution layer for open/close app + file CRUD (`sidecar/executor.py`)
- Per-action/target whitelist (`desktop/src/components/WhitelistSettings.jsx`)

## References
- `sidecar/handlers/base.py`, `registry.py`, `window_ops.py`
- `sidecar/handlers/chrome.py`, `vscode.py`
- `sidecar/brain.py`, `llm_providers.py`, `executor.py`, `app.py`
- `desktop/src/components/CommandApproval.jsx`, `WhitelistSettings.jsx`
