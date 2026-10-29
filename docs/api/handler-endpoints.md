# API Endpoint: App Handlers

## Overview
One endpoint that lists Rigel's registered per-app `AppHandler`s
(`sidecar/handlers/`) and the tools each exposes — the only way the
Settings UI knows what per-app whitelist sections to render, since the set
of handlers is entirely server-driven. Also documented here: the
`app_action`-related parts of the existing whitelist-config endpoints,
which `app_action` commands are checked against.

---

## `GET /api/rigel/handlers`

Returns every currently registered `AppHandler` and the tools it exposes,
for the Settings UI's per-app whitelist section
(`desktop/src/components/WhitelistSettings.jsx`).

### Parameters
None.

### Response (200)
```json
{
  "handlers": [
    {
      "app_id": "chrome",
      "display_name": "Google Chrome",
      "tools": [
        {"name": "new_tab", "description": "Open a new tab in Chrome's frontmost window (launching Chrome and/or opening a window first if none exists), optionally navigating it to a URL."},
        {"name": "close_tab", "description": "Close the active tab in Chrome's frontmost window."},
        {"name": "list_tabs", "description": "List the title and URL of every tab open in Chrome's frontmost window. Use this to answer questions like 'what tabs do I have open' — its result text is the answer, not just a status."},
        {"name": "new_window", "description": "Open a new Chrome window, optionally navigating its first tab to a URL."},
        {"name": "focus", "description": "Bring Chrome's window to the front."},
        {"name": "minimize", "description": "Minimize all of Chrome's open windows."}
      ]
    },
    {
      "app_id": "vscode",
      "display_name": "Visual Studio Code",
      "tools": [
        {"name": "open_file", "description": "Open a specific file in VS Code, in the current window if one is already open. Works for a file that doesn't exist yet, too."},
        {"name": "open_folder", "description": "Open a folder in VS Code as a workspace."},
        {"name": "new_window", "description": "Open a new, empty VS Code window with no file or folder loaded."},
        {"name": "focus", "description": "Bring VS Code's window to the front. VS Code must already be running."},
        {"name": "minimize", "description": "Minimize all of VS Code's open windows to the Dock."}
      ]
    }
  ]
}
```
Each tool entry is `{name, description}` only — the full Claude tool-use
`input_schema` (parameter types/requiredness) isn't included, since the
Settings UI only needs enough to render a checkbox per tool, not to
construct a call. `handlers` reflects whatever
`sidecar/handlers/registry.all_handlers()` currently holds, in
registration order (the order `sidecar/handlers/__init__.py` imports the
handler modules — currently `chrome.py`, then `vscode.py`).

### Error Responses
None specific to this endpoint — it always returns 200 with whatever the
registry currently holds (an empty `handlers: []` list is a valid, if
unlikely, response if no handler module registered successfully, not an
error state).

### Examples

#### cURL
```bash
curl http://127.0.0.1:5140/api/rigel/handlers | python3 -m json.tool
```

#### Python
```python
import requests

response = requests.get("http://127.0.0.1:5140/api/rigel/handlers")
for handler in response.json()["handlers"]:
    print(handler["app_id"], [t["name"] for t in handler["tools"]])
```

### Notes
- This is a read-only, always-cheap call (an in-process dict lookup, no
  I/O) — safe to call on every Settings panel mount, which is exactly what
  `WhitelistSettings.jsx` does (`getHandlers()` in `desktop/src/api.js`,
  called from a `useEffect` on mount).
- If the sidecar is unreachable, `WhitelistSettings.jsx` catches the
  fetch failure and simply renders no per-app section, rather than
  surfacing an error — the four fixed-action whitelist rows still render
  normally.

---

## `GET /api/rigel/settings/whitelist-config`

Returns the persisted whitelist config, including any `app_action`
entries, or an all-off default if never saved.

### Parameters
None.

### Response (200)
```json
{
  "open_app": {"all": false, "targets": []},
  "close_app": {"all": false, "targets": []},
  "create_file": {"all": false, "targets": []},
  "delete_file": {"all": false, "targets": []},
  "app_action": {
    "chrome": {"all": false, "tools": ["new_tab", "list_tabs"]},
    "vscode": {"all": true, "tools": []}
  },
  "click_menu_item": {}
}
```
`app_action` is a map keyed by `app_id` (not one of the four fixed action
keys above it), matching `sidecar/app.py`'s `AppActionWhitelist` model:
`{"all": bool, "tools": [str, ...]}`. `"all": true` auto-approves every
tool that app's handler currently exposes; otherwise only the tool names
listed in `"tools"` are auto-approved, and everything else for that app
still requires approval. An app with no entry at all in `app_action`
behaves the same as `{"all": false, "tools": []}` — nothing auto-approved.
(`click_menu_item` is a separate, unrelated whitelist key for the Menu
Actions feature — see [`docs/features/menu-actions.md`](../features/menu-actions.md)
— shown here only because it appears in the same response.)

---

## `POST /api/rigel/settings/whitelist-config`

Saves the whole whitelist config, including `app_action`. Takes effect on
the next `/chat` call — `app.py`'s `chat()` reads `whitelist_config` fresh
from `db.get_setting()` on every request, so no restart is needed.

### Request Body
The full `WhitelistConfig` shape — the four fixed-action entries plus
`app_action` (and `click_menu_item`). A partial body still works because
every field has a Pydantic default (`ActionWhitelist()`/`{}`), but a
`POST` **replaces the whole stored value**, so omitting `app_action`
entirely resets it to `{}` rather than leaving a previously-saved
per-app config untouched. The frontend always sends the full config object
it last fetched, with only the relevant field(s) changed, to avoid this.

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `open_app`, `close_app`, `create_file`, `delete_file` | `{all, targets}` | no | Same shape as before this feature — unaffected by `app_action`. |
| `app_action` | `{app_id: {all, tools}}` | no | Per-app auto-approve rules for `AppHandler`-produced commands. Default `{}`. |
| `click_menu_item` | `{app: {all, menu_paths}}` | no | Unrelated to this feature — see the Menu Actions docs. |

### Request Body Example
```json
{
  "open_app": {"all": true, "targets": []},
  "close_app": {"all": false, "targets": []},
  "create_file": {"all": false, "targets": []},
  "delete_file": {"all": false, "targets": []},
  "app_action": {
    "chrome": {"all": false, "tools": ["new_tab", "list_tabs"]}
  },
  "click_menu_item": {}
}
```

### Response
- **200:** `{"ok": true}`
- **422:** malformed body (e.g. `app_action.chrome.tools` not a list of
  strings) — standard FastAPI/Pydantic validation error, not a
  hand-written 400 the way `llm-config`'s validation is. There is no
  additional application-level validation on `app_action` beyond the
  Pydantic model shape — an `app_id`/`tool` name that doesn't correspond
  to any currently-registered handler is accepted and stored, and simply
  never matches anything at whitelist-check time
  (`executor.is_whitelisted()` looks it up by exact key; a stale or
  misspelled `app_id` just means nothing auto-approves for it).

#### Example cURL
```bash
curl -X POST http://127.0.0.1:5140/api/rigel/settings/whitelist-config \
  -H "Content-Type: application/json" \
  -d '{
    "open_app": {"all": false, "targets": []},
    "close_app": {"all": false, "targets": []},
    "create_file": {"all": false, "targets": []},
    "delete_file": {"all": false, "targets": []},
    "app_action": {"chrome": {"all": true, "tools": []}},
    "click_menu_item": {}
  }'
```

### Python
```python
import requests

config = requests.get(
    "http://127.0.0.1:5140/api/rigel/settings/whitelist-config"
).json()
config["app_action"].setdefault("chrome", {"all": False, "tools": []})
config["app_action"]["chrome"]["tools"].append("new_tab")

requests.post(
    "http://127.0.0.1:5140/api/rigel/settings/whitelist-config",
    json=config,
)
```

## Notes
- Whitelisting is checked inside `POST /chat` (`executor.is_whitelisted()`)
  before a command is even logged as `"pending"` — a whitelisted
  `app_action` command runs immediately and comes back with status `"ok"`/
  `"error"` in the same `/chat` response, never as a separate approval
  step. See `docs/api/llm-settings-endpoints.md` for the sibling settings
  endpoints (`llm-config`, `llm-options`) this feature doesn't change.
- No rate limiting on any of these endpoints — `GET /handlers` is an
  in-memory lookup, and the whitelist endpoints are ordinary SQLite
  reads/writes through `db.get_setting`/`db.set_setting`.
- Related: [`docs/features/app-handlers.md`](../features/app-handlers.md),
  [`docs/architecture/app-handlers.md`](../architecture/app-handlers.md).
