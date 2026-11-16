# Architecture: App Handlers (`AppHandler` Framework)

## Purpose
Lets Rigel operate *inside* an app it already knows how to open/close —
a new Chrome tab, a folder opened in VS Code — by giving each app its own
small, LLM-backed "sub-agent": a fixed system prompt and Claude tool-use
schema, matched by keyword and dispatched through the same
preview/whitelist/execute/log pipeline every other Rigel command already
uses. `sidecar/handlers/base.py`'s own docstring frames the problem this
solves precisely: the original executor speaks a fixed, four-verb
vocabulary resolved by one shared LLM call, which is enough to launch or
quit an app but not to operate inside one.

## High-Level Diagram
```
┌──────────────────────┐
│   User utterance      │
└──────────┬────────────┘
           ▼
┌───────────────────────────────────────────────────────┐
│  sidecar/brain.py : respond()                          │
│  ┌─────────────────────────┐   ┌──────────────────────┐│
│  │ shared four-verb pass    │   │ _app_commands()       ││
│  │ (open/close/create/del)  │   │  registry.match(text) ││
│  └─────────────┬─────────────┘   └──────────┬────────────┘│
│                │ reply + commands            │ app_id match │
│                │                              ▼              │
│                │              ┌─────────────────────────────┐│
│                │              │ llm_providers.claude_app_    ││
│                │              │ action(text, model, handler) ││
│                │              │  Claude tool-use call scoped ││
│                │              │  to handler.system_prompt +  ││
│                │              │  handler.tools                ││
│                │              └──────────────┬────────────────┘│
│                │                              │ zero/one app_action │
│                ▼                              ▼                    │
│              commands = shared_commands + app_action_commands       │
└──────────────────────────────┬────────────────────────────────────┘
                                ▼
┌───────────────────────────────────────────────────────────────────┐
│  sidecar/executor.py                                                │
│  preview() ──▶ is_whitelisted() ──▶ execute() ──▶ db.log_command()   │
│  (validates          (per app_id,        (handler.execute_tool       │
│   app_id/tool          not per            → osascript / code CLI)     │
│   against              generic                                        │
│   handler.tools)       action key)                                    │
└───────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                     sidecar/handlers/registry.py
                     (holds the live AppHandler instances:
                      ChromeHandler, VSCodeHandler, ...)
```

## Components

### `sidecar/handlers/base.py` — `AppHandler` (ABC)
- **Language:** Python
- **Location:** `sidecar/handlers/base.py`
- **Purpose:** The contract every concrete handler implements: four
  class-level attributes plus one method.
  ```python
  class AppHandler(ABC):
      app_id: str
      display_name: str
      match_keywords: list[str]
      system_prompt: str
      tools: list[dict]

      @abstractmethod
      def execute_tool(self, tool_name: str, tool_input: dict) -> tuple[str, str]:
          raise NotImplementedError
  ```
  Instances are stateless and safe to share as module-level singletons —
  each concrete handler module registers exactly one instance at import
  time. `execute_tool` must never raise: it follows the same
  `(status, detail)` contract as `executor._execute_macos`, since a
  handler catching its own expected failure modes (app not running,
  AppleScript error) and reporting them as `("error", ...)` is more useful
  to the user than a stack trace, even though `executor.execute()` also
  wraps every call in a last-resort `try/except` as a backstop.
- **Dependencies:** stdlib `abc` only.
- **Public Interface:** the `AppHandler` class itself; concrete
  subclasses live in `chrome.py`/`vscode.py`.

### `sidecar/handlers/registry.py` — matching + lookup
- **Language:** Python
- **Location:** `sidecar/handlers/registry.py`
- **Purpose:** A module-level `dict[str, AppHandler]` (`_HANDLERS`),
  populated by each handler module's `registry.register(...)` call at
  import time (triggered by `sidecar/handlers/__init__.py` importing every
  handler module — importing the `handlers` package is enough to populate
  the registry). `match(text)` does a **substring match** of each
  handler's `match_keywords` against the lowercased text, with the
  *longest matching keyword* winning ties (so `"google chrome"` beats
  `"chrome"` when both are present in the utterance), and registration
  order breaking any further tie. Returns `None` if nothing matches, so
  `brain.py` can skip the per-app LLM call entirely for text that clearly
  isn't about any known app — this is a small, real optimization: not
  every chat turn pays for a second Claude call.
- **Dependencies:** `sidecar.handlers.base.AppHandler`.
- **Public Interface:** `register(handler)`, `get(app_id) -> AppHandler |
  None`, `all_handlers() -> list[AppHandler]`, `match(text) -> AppHandler
  | None`.

### `sidecar/handlers/window_ops.py` — shared AppleScript helpers
- **Language:** Python
- **Location:** `sidecar/handlers/window_ops.py`
- **Purpose:** "Bring this app's window to the front" and "minimize it"
  are the same System Events AppleScript regardless of which app it is,
  so both `ChromeHandler` and `VSCodeHandler` delegate their `focus`/
  `minimize` tools here instead of each re-implementing the same
  AppleScript. `is_running()` is a best-effort check (`False` on any
  AppleScript error, never raises) used only to produce a friendlier error
  message before an operation that would otherwise fail opaquely — e.g.
  `ChromeHandler._close_tab()` checks it first so "Chrome isn't running"
  reads better than a raw AppleScript stack trace from `close active tab
  of window 1` on a window-less Chrome.
- **Dependencies:** stdlib `subprocess` (shells out to `osascript`).
- **Public Interface:** `focus(app_name) -> (status, detail)`,
  `minimize(app_name) -> (status, detail)`, `is_running(app_name) -> bool`.

### `sidecar/brain.py` — `_app_commands()` (modified)
- **Purpose:** The router step that connects `registry.match()` to
  `llm_providers.claude_app_action()`:
  ```python
  def _app_commands(text: str, llm_config: dict) -> list[dict]:
      handler = registry.match(text)
      if handler is None:
          return []
      try:
          return llm_providers.claude_app_action(text, llm_config["claude_model"], handler)
      except llm_providers.LLMError as e:
          logger.warning("App handler '%s' call failed (%s); skipping.", handler.app_id, e)
          return []
  ```
  Called from `_respond_via_provider()`'s Claude branch only (`reply,
  commands = ...; return reply, commands + _app_commands(text,
  llm_config)`), additively — a handler failure never blocks or replaces
  the reply/commands the shared four-verb pass already produced; an empty
  list from `_app_commands()` is a normal outcome (no match, or a
  well-behaved handler correctly deciding nothing in its `tools` applies),
  not a fallback condition the way `LLMError` is elsewhere in this module.

### `sidecar/llm_providers.py` — `claude_app_action()` (new)
- **Purpose:** A second Claude entry point alongside `claude_respond()`,
  using real tool-use instead of the shared `RESPONSE_SCHEMA` structured-
  output trick:
  ```python
  def claude_app_action(text: str, model: str, handler: AppHandler) -> list[dict]:
      ...
      response = client.messages.create(
          model=model,
          max_tokens=512,
          system=handler.system_prompt,
          tools=handler.tools,
          tool_choice={"type": "auto"},
          messages=[{"role": "user", "content": text}],
      )
      ...
      commands = []
      for block in response.content:
          if block.type == "tool_use":
              commands.append({
                  "action": "app_action",
                  "args": {"app_id": handler.app_id, "tool": block.name, "tool_args": block.input},
              })
      return commands
  ```
  Unlike `claude_respond()`, this call produces no reply text —
  `brain.py` already has one from the shared pass — it exists purely to
  let a handler's own varying `tools` list decide whether the utterance
  maps to one of *its* actions. Same error handling as `claude_respond()`
  (auth/rate-limit/connection/status/credentials errors all normalized to
  `LLMError`), and the same `anthropic.Anthropic()` client construction
  (env-resolved credentials, no key stored by Rigel).

### `sidecar/executor.py` — `app_action` branch (modified)
- **Purpose:** `preview()`, `is_whitelisted()`, and `_execute_macos()`
  each gained one more action to recognize, using the same contract as
  the original four:
  - `preview("app_action", args)` requires non-empty `app_id`/`tool`,
    looks the handler up via `registry.get(app_id)` (raising
    `UnsafeCommandError` if unregistered), and validates `tool` is one of
    `{t["name"] for t in handler.tools}` — the same defense-in-depth as
    validating a file path resolves inside the sandbox, applied to a
    handler's declared vocabulary instead.
  - `is_whitelisted("app_action", resolved_args, whitelist)` looks up
    `whitelist["app_action"][app_id]` — a different key shape from the
    other four actions' `{action: {all, targets}}`, deliberately: "auto-
    approve Chrome's new-tab" shouldn't also auto-approve VS Code opening
    arbitrary folders, so whitelisting is per-app (`{app_id: {all,
    tools}}`), not per-generic-action.
  - `_execute_macos("app_action", args)` looks the handler up again (by
    design — `preview` and `execute` are separate calls in `app.py`'s
    `/chat` and `/commands/{id}/approve` handlers, so `execute` can't
    assume the handler found during `preview` is still the same object
    without re-resolving it) and calls `handler.execute_tool(args["tool"],
    args.get("tool_args") or {})`.
- **Dependencies:** `sidecar.handlers.registry` (added import).

### `sidecar/app.py` — `GET /api/rigel/handlers`, whitelist model
- **Purpose:** `list_handlers()` returns every registered handler's
  `app_id`/`display_name`/`tools` (name + description only, not the full
  `input_schema` — the Settings UI only needs enough to render checkboxes)
  for `WhitelistSettings.jsx` to build its per-app section without any
  hardcoded knowledge of which handlers exist. `AppActionWhitelist`
  (`{all: bool, tools: list[str]}`) and `WhitelistConfig.app_action:
  dict[str, AppActionWhitelist]` are the Pydantic models backing that
  whitelist shape — see the API doc for the full request/response detail.

### `desktop/src/components/WhitelistSettings.jsx` / `CommandApproval.jsx` (modified)
- **Purpose:** `WhitelistSettings.jsx` fetches `getHandlers()` on mount
  and renders one section per handler below the four fixed actions,
  independent of them (it has no static knowledge of which apps have
  handlers — that list is entirely server-driven).
  `CommandApproval.jsx`'s `describe(cmd)` gained an `app_action` branch:
  `` `${app_id}: ${label}${detail ? ` (${detail})` : ""}` `` — e.g.
  `"chrome: new tab (github.com)"` — reusing the pattern already used for
  the four fixed actions rather than inventing a new card layout.

## Data Flow

### Primary Flow: an in-app action
```
1. User: "new tab in Chrome to github.com"
2. brain.py's shared four-verb pass finds nothing (no open/close/file verb)
3. registry.match() finds ChromeHandler ("chrome" keyword substring hit)
4. claude_app_action() calls Claude with ChromeHandler.system_prompt +
   ChromeHandler.tools; Claude returns a tool_use block: new_tab({"url": "github.com"})
5. brain.py wraps it: {"action": "app_action", "args": {"app_id": "chrome",
   "tool": "new_tab", "tool_args": {"url": "github.com"}}}
6. app.py's /chat handler: executor.preview() validates app_id + tool
7. executor.is_whitelisted() checks whitelist["app_action"]["chrome"]
8. Not whitelisted → status "pending", approval card renders
9. User approves → executor.execute() → ChromeHandler.execute_tool("new_tab", {...})
   → osascript creates the tab → ("ok", "Opened a new tab at github.com.")
10. db.update_command_status() records the outcome
```

### Secondary Flow: text that isn't an in-app action
```
1. User: "open Chrome"
2. brain.py's shared four-verb pass matches open_app({"target": "Chrome"})
3. registry.match() still finds ChromeHandler (keyword "chrome" present)
4. claude_app_action() is still called — but ChromeHandler.system_prompt
   explicitly instructs Claude to call nothing when the request is about
   launching/quitting the whole app, not an in-app action
5. Claude's response has no tool_use block → _app_commands() returns []
6. Final commands = [open_app] only — the generic path, not a redundant
   or conflicting app_action
```
This second flow is deliberate, not incidental: both `chrome.py` and
`vscode.py`'s system prompts explicitly instruct the model to call no tool
at all when the utterance is really about launching or quitting the
app, so the shared four-verb pass and the handler's scoped call never
fight over the same intent. There is no code-level de-duplication between
the two passes — the design relies entirely on each handler's system
prompt drawing the line correctly (see Alternative Approaches Considered
in `docs/proposals/expanded-app-control.md` for the general shape of this
decision, and the source doc's Known Limitations for the corresponding
caveat that `registry.match()` still runs the handler's LLM call on text
that only launches the app).

### Error Handling
Every failure mode in the new call path — Claude auth/rate-limit/
connection/status errors from `claude_app_action()`, an app_id with no
registered handler, a tool name not in `handler.tools`, an
`execute_tool()` internal failure (AppleScript error, `code` CLI missing)
— converts to the same two vocabularies already used elsewhere in the
codebase: `LLMError` for anything from the LLM call (caught in
`_app_commands()`, logged as a warning, treated as "no app_action
commands," never surfaced to the user as an error), and `UnsafeCommandError`
/ `("error", detail)` for anything from validation or execution (caught by
`app.py`'s `/chat` handler the same way as any other action's failure).
No new exception types were introduced for this feature — it reuses the
two the rest of the execution layer already has.

## Concurrency & State Management
No new concurrency concerns. `AppHandler` instances are stateless
singletons (no per-request state stored on the handler object itself), and
`executor.execute()`'s `app_action` branch re-resolves the handler by
`app_id` via `registry.get()` on every call rather than caching a
reference from `preview()`, so there's no risk of acting on a stale
handler object across the `preview` → approve (possibly much later, after
a user reviews a pending command) → `execute` gap. Everything downstream
(the `subprocess.run()` calls in `window_ops.py`/`chrome.py`/`vscode.py`)
is synchronous and blocking, matching every other execution path in
`executor.py` — FastAPI still handles one request at a time in this app,
so this introduces no new synchronization surface.

## Performance Characteristics
- `registry.match()` is an O(handlers × keywords) substring scan over
  short strings — negligible even with many more handlers than the two
  that exist today.
- `claude_app_action()` is a full extra Claude API round trip on top of
  `claude_respond()`'s — i.e. a chat turn that matches a handler's keyword
  costs two model calls, not one, whether or not the handler ultimately
  produces a command. This is the direct cost of "ask each matched app's
  own sub-agent," same tradeoff Claude Code itself accepts when it
  delegates to a subagent instead of keeping everything in one context.
- Handler execution itself (`osascript`, the `code` CLI) is a blocking
  subprocess call, same latency profile as every other `_execute_macos`
  branch — no async execution anywhere in this layer yet.

## External Dependencies
| Dependency | Version | Purpose | License |
|-----------|---------|---------|---------|
| `anthropic` | >=0.69 | Same Claude SDK client `claude_respond()` already uses — `claude_app_action()` adds no new dependency | MIT |
| macOS `osascript` (system binary) | n/a | AppleScript execution for `window_ops.py` and `chrome.py`'s Chrome-specific scripting | Apple, system-provided |
| VS Code `code` CLI (external, user-installed) | n/a | `vscode.py`'s `open_file`/`open_folder`/`new_window` — not a Python package dependency, an expected-on-PATH external tool | MIT (VS Code) |

## Alternative Approaches Considered

- **A single shared JSON schema (like `RESPONSE_SCHEMA`) covering every
  app's actions, instead of per-handler Claude tool-use:** Rejected.
  `RESPONSE_SCHEMA`'s four-action `enum` works because there are exactly
  four generic verbs, all apps share. App-specific actions don't share a
  vocabulary at all — Chrome's `new_tab(url)` and VS Code's
  `open_folder(path)` have nothing in common — so a single schema would
  either need every app's fields unioned into one giant always-mostly-
  empty object, or a discriminated-union shape Claude's structured-output
  validator doesn't cleanly support with `additionalProperties: false`
  enforced per node (the same constraint that already forced `args` to
  become `args_json` in the shared schema — see
  `docs/architecture/llm-provider-selection.md`'s own "Alternative
  Approaches" entry on that). Real Claude tool-use, scoped per handler via
  its own `tools` list, sidesteps this entirely: each handler's schema
  only ever needs to describe its own actions.

- **Whitelisting `app_action` by the same `{action: {all, targets}}` shape
  as the four fixed actions, keyed by a flattened string like
  `"chrome.new_tab"`:** Rejected in favor of the per-app-id, nested
  `{app_id: {all, tools}}` shape actually built. A flattened key would
  work but loses the natural "allow all of this app's actions" toggle
  (`all: true` for `chrome` covering `new_tab`/`close_tab`/... without
  enumerating them) that the nested shape gets for free, and it matches
  how `GET /handlers` already groups tools under each handler — the
  whitelist config's shape mirrors the API response's shape rather than
  inventing a third one.

- **A generic `AppHandler` for menu-bar/window operations across *any*
  running app, instead of two hand-written per-app handlers (Chrome, VS
  Code):** Considered, and explicitly the direction a later feature took
  — but not as another `AppHandler`. `AppHandler.tools` is a **fixed
  class-level list, set at class-definition time** — right for a
  well-known, stable vocabulary like Chrome's tabs or VS Code's file/
  folder opening, but wrong for "whatever this app's menu bar currently
  contains," which is dynamic and app-state-dependent (a greyed-out Edit
  menu item, an app-specific submenu that doesn't exist until some other
  state is true). Modeling a live-discovered menu as a fixed `tools` list
  would mean re-declaring `tools` per app per session, which the
  `AppHandler` contract has no hook for. This is recorded as the
  "Architectural Decision" in `docs/proposals/menu-actions.md`, which
  chose instead to give menu-bar clicking its own module
  (`sidecar/handlers/menu_actions.py`, *not* an `AppHandler` subclass),
  matched by a fallback step in `brain.py` rather than
  `registry.match()`'s keyword lookup — engaged only after both the
  shared four-verb pass and `registry.match()` (this framework) come back
  empty. See [`docs/architecture/menu-actions.md`](menu-actions.md) for
  that feature's own design detail; it is documented separately and is
  out of scope here beyond this one architectural fork.

## Future Improvements
- Route `registry.match()`'s keyword-substring gap (an utterance that's
  conversationally clear but names no known keyword) through the LLM
  instead, at the cost of an extra call on every turn rather than just
  matched ones.
- Extend `claude_app_action()`'s pattern to Ollama once local models gain
  a usable tool-use equivalent to JSON mode.
- A generic window-ops-only handler (focus/minimize) for apps that don't
  need a bespoke tool set, so `window_ops.py`'s helpers aren't only
  reachable through a full custom handler.

## Testing Strategy
- **Unit tests:** none exist in this repo yet, for this feature or any
  other sidecar module (matches the project's current state — see
  `docs/architecture/llm-provider-selection.md`'s own Testing Strategy
  section making the same note for the LLM brain).
- **Manual/smoke, scratch venv:** the framework layer — `registry.match()`
  keyword resolution, `executor.preview()`/`is_whitelisted()`'s new
  `app_action` branches, the `whitelist_config.app_action` shape
  round-tripping through `GET`/`POST /settings/whitelist-config`, `GET
  /handlers`'s response shape, and the desktop frontend building cleanly
  against `WhitelistSettings.jsx`/`CommandApproval.jsx`'s new code — was
  exercised this way. This confirms the wiring is internally consistent;
  it does not confirm behavior against a real macOS environment.
- **Not yet verified on real hardware:** every concrete `osascript` call
  the two handlers make (`ChromeHandler`'s new tab/close tab/list tabs/
  new window, both handlers' `focus`/`minimize` via `window_ops.py`), the
  `code` CLI calls in `vscode.py`, and a live (non-mocked) Claude
  tool-use round trip through `claude_app_action()`. This is the same gap
  called out in the feature doc's Testing section and is the honest state
  of this feature as of this writing — contrast with the separate Menu
  Actions feature (`docs/architecture/menu-actions.md`), several slices of
  which did get live-hardware verification.

## References
- [`docs/features/app-handlers.md`](../features/app-handlers.md)
- [`docs/api/handler-endpoints.md`](../api/handler-endpoints.md)
- [`docs/troubleshooting/app-handlers.md`](../troubleshooting/app-handlers.md)
- `docs/proposals/expanded-app-control.md` — original design proposal
- `docs/proposals/menu-actions.md` — the "Architectural Decision" section
  recording why menu-bar clicking became its own module, not another
  `AppHandler`
- [`docs/architecture/menu-actions.md`](menu-actions.md) — that feature's
  own architecture doc
- `sidecar/handlers/base.py`, `registry.py`, `window_ops.py`, `chrome.py`,
  `vscode.py`
- `sidecar/brain.py`, `llm_providers.py`, `executor.py`, `app.py`
- `desktop/src/components/WhitelistSettings.jsx`, `CommandApproval.jsx`,
  `desktop/src/api.js`
