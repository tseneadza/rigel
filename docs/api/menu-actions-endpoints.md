# API Endpoint: App Menu Actions

## Overview
One endpoint backing the orb window's **▤** running-apps dropdown and the
"what apps are open" chat query, plus the `click_menu_item` slice of the
existing whitelist-config endpoints (shared with every other whitelistable
action — `open_app`, `close_app`, `create_file`, `delete_file`,
`app_action`).

---

## `GET /api/rigel/running-apps`

Every foreground (non-background-only) app currently running, by process
name — the same identifiers `sidecar.handlers.menu_actions.frontmost_app()`
and `discover_menu()` use. macOS only.

### Parameters
None.

### Response (200)
```json
{
  "apps": ["Finder", "Google Chrome", "iTerm2", "Rigel", "TextEdit"]
}
```

### Error Responses
- **503 Service Unavailable:** System Events couldn't be reached — no
  macOS (`osascript` missing entirely), or another AppleScript failure.
  The `detail` field carries a clean, human-readable message (never a raw
  AppleScript error string).

```json
{
  "detail": "'osascript' isn't available on this machine — App Menu Actions is macOS-only, same as the rest of Rigel's execution layer."
}
```

Note: unlike `discover_menu()` (used internally by the `click_menu_item`
flow), this endpoint's underlying call —
`menu_actions.list_running_apps()` — does **not** require the macOS
Accessibility permission grant; it only ever returns a 503 for "no macOS
at all" or an unexpected AppleScript error, confirmed live.

### Examples

```bash
curl http://127.0.0.1:5140/api/rigel/running-apps
```

```python
import requests

response = requests.get("http://127.0.0.1:5140/api/rigel/running-apps")
print(response.json())
# {"apps": ["Finder", "Google Chrome", "iTerm2", "Rigel", "TextEdit"]}
```

---

## `GET /api/rigel/settings/whitelist-config` (`click_menu_item` fields)

Returns the persisted whitelist config, or the Pydantic model's defaults
if never saved. This is the same endpoint every other whitelistable
action uses — documented here only for the `click_menu_item` slice of its
shape.

### Response (200) — relevant fields only
```json
{
  "open_app": { "all": false, "targets": [] },
  "close_app": { "all": false, "targets": [] },
  "create_file": { "all": false, "targets": [] },
  "delete_file": { "all": false, "targets": [] },
  "app_action": {},
  "click_menu_item": {
    "Google Chrome": {
      "all": false,
      "menu_paths": [["Window", "Close All"]]
    }
  }
}
```
`click_menu_item` is keyed by app process name (the same identifier
`GET /running-apps` returns), not globally — matching `app_action`'s
per-`app_id` shape rather than the flat `{"all", "targets"}` shape the
original four actions use, since "auto-approve Chrome's Window > Close
All" shouldn't also auto-approve every other app's menu clicks.

---

## `POST /api/rigel/settings/whitelist-config` (`click_menu_item` fields)

Saves the full whitelist config (all actions at once — this endpoint takes
the entire `WhitelistConfig` object, not a per-action patch). Takes effect
on the next command whose action is checked against it.

### Request Body
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `click_menu_item` | object | no | `{app_process_name: {"all": bool, "menu_paths": [[str, ...], ...]}}`. Every other top-level field (`open_app`, `close_app`, `create_file`, `delete_file`, `app_action`) is also required by the model but keeps its existing shape — see `docs/api/` for those, or `sidecar/app.py`'s `WhitelistConfig`. |

```json
{
  "open_app": { "all": false, "targets": [] },
  "close_app": { "all": false, "targets": [] },
  "create_file": { "all": false, "targets": [] },
  "delete_file": { "all": false, "targets": [] },
  "app_action": {},
  "click_menu_item": {
    "Google Chrome": { "all": true, "menu_paths": [] }
  }
}
```

### Response
- **200:** `{"ok": true}`
- **422 Unprocessable Entity:** malformed body — e.g. `menu_paths` isn't a
  list of lists of strings (standard FastAPI/Pydantic validation error
  shape, not a custom Rigel error).

**Important — the `is_dangerous()` override.** Setting `"all": true` for
an app does **not** auto-approve every menu click for it. Before
consulting this whitelist at all, `executor.is_whitelisted()` checks
`menu_actions.is_dangerous(menu_path)` — a menu path containing a
dangerous-sounding word (delete, erase, empty trash, format, quit,
uninstall, remove, discard, reset, wipe, destroy, anywhere in the path's
text) always requires manual approval, regardless of `all` or
`menu_paths`. This is the only action in `WhitelistConfig` where the
whitelist can be overridden this way — see
[`docs/architecture/menu-actions.md`](../architecture/menu-actions.md#alternative-approaches-considered)
for why.

### Examples

```bash
curl -X POST http://127.0.0.1:5140/api/rigel/settings/whitelist-config \
  -H "Content-Type: application/json" \
  -d '{
    "open_app": {"all": false, "targets": []},
    "close_app": {"all": false, "targets": []},
    "create_file": {"all": false, "targets": []},
    "delete_file": {"all": false, "targets": []},
    "app_action": {},
    "click_menu_item": {
      "Google Chrome": {"all": false, "menu_paths": [["Window", "Close All"]]}
    }
  }'
```

```python
import requests

current = requests.get(
    "http://127.0.0.1:5140/api/rigel/settings/whitelist-config"
).json()
current["click_menu_item"]["TextEdit"] = {"all": True, "menu_paths": []}
requests.post(
    "http://127.0.0.1:5140/api/rigel/settings/whitelist-config",
    json=current,
)
```

## Notes
- There's currently no Settings UI section for populating
  `click_menu_item` (unlike `app_action`, which is fed by the fixed,
  enumerable list from `GET /handlers`) — the examples above are the only
  way to set it today. See the feature doc's Known Limitations.
- `GET /running-apps` is fetched fresh on every dropdown open by
  `RunningApps.jsx`, not polled continuously — cheap enough (a single flat
  System Events query, no per-app tree walk) that this isn't a performance
  concern, but there's no push/websocket path if an app quits while the
  dropdown is open.
- No rate limiting on any of these endpoints.
- Related: [`docs/features/menu-actions.md`](../features/menu-actions.md),
  [`docs/architecture/menu-actions.md`](../architecture/menu-actions.md),
  [`docs/troubleshooting/menu-actions.md`](../troubleshooting/menu-actions.md).
