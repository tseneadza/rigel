# Troubleshooting Guide: App Menu Actions

## Quick Diagnosis

```
Is the sidecar even running the App Menu Actions code at all?
│
├─ `curl http://127.0.0.1:5140/api/rigel/running-apps` returns 404
│  → the sidecar is running OLD code. See "Sidecar needs a manual restart
│    after git pull" below — this is not a bug, it's a stale process.
│
└─ It returns 503 with a "detail" message
   ├─ "'osascript' isn't available on this machine..."
   │  → see "osascript missing entirely" below.
   ├─ "Rigel doesn't have Accessibility permission yet..."
   │  → see "Accessibility permission not granted" below.
   └─ Something else / "'<App>' isn't running."
      → see "AppleScript error codes this module translates" below.
```

## Common Issues

### Issue: Sidecar needs a manual restart after `git pull`
**Symptoms:** You just pulled a change that touches
`sidecar/handlers/menu_actions.py`, `sidecar/brain.py`, `sidecar/app.py`,
or `sidecar/executor.py` — but `GET /api/rigel/running-apps` still 404s,
or a "what apps are open?" chat query still gets the old canned stub
reply instead of a real list.

**Cause:** this is not a bug in the feature — the sidecar is a plain
Python process (`python3 -m sidecar`) with **no auto-reload**. Unlike the
Vite frontend dev server (`npm run dev`), which hot-reloads on file
change automatically, a running sidecar process keeps serving whatever
code was loaded when it started, indefinitely, even after the files on
disk change underneath it. This caused real, live confusion during this
feature's own development: after `git pull`ing Slice 2's changes, the
sidecar kept returning a 404 on `/running-apps` and the pre-Slice-2 stub
reply for the chat query, until it was manually restarted.

**Diagnosis:**
```bash
# Confirm the sidecar process is actually old — check when it started
ps -o pid,lstart,command -p $(pgrep -f "python3 -m sidecar")
```

**Solutions:**
```bash
# Kill and restart from the same shell that has your env vars set
pkill -f "python3 -m sidecar"
./.venv/bin/python -m sidecar
```
Worth remembering for *every* future sidecar-side change, not just this
feature — the frontend's hot-reload can make it easy to forget the
backend doesn't have the same behavior.

### Issue: Accessibility permission not granted
**Symptoms:** `discover_menu()`/`click_menu_item()` (via
`MenuDiscoveryError` or an `("error", ...)` execute result) or
`GET /api/rigel/running-apps` returns:
```
Rigel doesn't have Accessibility permission yet — grant it in
System Settings -> Privacy & Security -> Accessibility, then retry.
```
This is macOS's error **-1719** ("not allowed assistive access"),
translated into a clean message — `menu_actions._permission_denied()`
matches on both the human-readable phrase and the raw code, since macOS's
exact wording has varied across versions.

**What happens without the grant:** `frontmost_app()`/
`list_running_apps()` work fine with **no** grant at all — confirmed live,
these only query System Events' own process list, not a specific app's UI
elements. It's specifically `discover_menu()` (and therefore
`click_menu_item()`, and therefore any spoken action that falls through to
the menu-actions layer) that needs it — walking another app's Accessibility
tree is the operation macOS gates.

**Diagnosis:** try the standalone discovery script directly — it surfaces
the same error with no other moving parts:
```bash
python3 -m sidecar.handlers.menu_actions "TextEdit"
```

**Solutions:**
1. Open **System Settings → Privacy & Security → Accessibility**.
2. Grant access to whatever process actually runs the sidecar — this is
   your terminal app (Terminal.app, iTerm2, etc.) if you launch the
   sidecar from a shell, or the packaged Rigel app if it launches the
   sidecar itself. Granting it to the wrong process (e.g. only to
   `python3` when your terminal app is what needs it, on some macOS
   versions) is a common near-miss — if the prompt doesn't appear and the
   error persists, check that the *actual parent process* is listed and
   checked.
3. Retry — no restart needed for this one, the permission takes effect
   immediately, unlike code changes (see the sidecar-restart issue above).

### Issue: AppleScript error codes this module translates
**Symptoms:** a raw-looking AppleScript failure instead of Rigel's own
clean message, or you're trying to understand what a logged error means.

`sidecar/handlers/menu_actions.py` recognizes exactly two error codes and
turns them into specific messages; anything else falls through to the raw
`stderr` text (still better than a traceback, but not specially handled):

| Code | Meaning | Rigel's message |
|------|---------|------------------|
| `-1719` | "not allowed assistive access" — Accessibility permission not granted | "Rigel doesn't have Accessibility permission yet — grant it in System Settings -> Privacy & Security -> Accessibility, then retry." |
| `-1728` | "Can't get process `<name>`" — named app isn't running | `"'<App>' isn't running."` |

**Diagnosis:** if you're seeing an *un*translated AppleScript error (raw
text, not one of the two messages above), it's a real, different failure
— run the same script manually to see the full text:
```bash
osascript -e 'tell application "System Events" to tell process "SomeApp" to name of menu bar 1'
```

**Solutions:**
- `-1719` → grant Accessibility (see above).
- `-1728` → the app named in your phrase (or resolved as frontmost) isn't
  actually running. Open it first, or check what `frontmost_app()`/
  `list_running_apps()` actually report:
  ```bash
  curl http://127.0.0.1:5140/api/rigel/running-apps
  ```
- Anything else → treat it as an ordinary AppleScript failure; the exact
  `stderr` text is preserved in the error detail rather than swallowed.

### Issue: `osascript` missing entirely
**Symptoms:**
```
'osascript' isn't available on this machine — App Menu Actions is
macOS-only, same as the rest of Rigel's execution layer.
```
on `discover_menu()`, `click_menu_item()`, `frontmost_app()`,
`list_running_apps()`, or a 503 from `GET /api/rigel/running-apps`.

**Cause:** `osascript` is a macOS-only system binary — it doesn't exist
on Linux or Windows at all. This repo's own non-macOS development
sessions hit exactly this (there's no way around it short of running on
real macOS): `_run_osascript()` catches the resulting `FileNotFoundError`
and re-raises it as a clean `MenuDiscoveryError` instead of letting a raw
traceback propagate, so at least the failure is legible even where the
feature fundamentally can't run.

**Solutions:**
- There isn't a workaround — App Menu Actions is macOS-only, same as
  `open_app`/`close_app`/the rest of Rigel's execution layer. Developing
  or testing the AppleScript-touching parts of this feature requires an
  actual Mac; everything else (fuzzy-match logic, the executor's
  validation/whitelist logic, the API shapes) can be developed and tested
  with `menu_actions` calls mocked out, which is how this feature's own
  Slice 3/4 logic was verified in a non-macOS environment.

### Issue: `click_menu_item` command never shows an approval card
**Symptoms:** you say something that should map to a menu action, but no
approval card appears and the reply doesn't mention a menu action either.

**Diagnosis:** this can be several different quiet no-ops by design (see
`_menu_action_commands()`'s docstring in `sidecar/brain.py`) — none of
them surface as a user-visible error, since this fallback is best-effort
on top of an already-complete reply:
- The shared four-verb pass or an `AppHandler` (Chrome/VS Code) already
  produced a command — menu actions only run when there are **zero**
  commands so far. Check the reply/logs for what Rigel actually detected.
- `_MENU_ACTION_VERB_HINT` didn't match your phrasing at all — it's a
  fixed verb list (close, open, new, save, copy, paste, ...); a phrase
  with none of those words never reaches menu discovery.
- No target app could be resolved (nothing named in the text, and
  `frontmost_app()` returned `None` or raised).
- `discover_menu()` raised (Accessibility not granted, app not running) —
  see the issues above.
- `fuzzy_match()` found nothing above its confidence threshold — the
  phrase genuinely doesn't match anything in that app's menu bar.

**Solutions:**
- Check the sidecar's console output — `respond()`'s own code path
  doesn't log at each quiet no-op today, so the fastest way to isolate
  which case you hit is to call the pieces directly:
  ```bash
  ./.venv/bin/python -c "
  from sidecar.handlers import menu_actions
  app = menu_actions.frontmost_app()
  print('target app:', app)
  menu = menu_actions.discover_menu(app)
  print(len(menu), 'menu items')
  print(menu_actions.fuzzy_match('your phrase here', menu))
  "
  ```
- If `fuzzy_match()` returns more than one candidate, that's a genuine
  tie, not a bug — Rigel deliberately doesn't guess; the reply should
  contain a note naming the candidates instead.

## Advanced Debugging

### Run discovery standalone, no chat/HTTP layer involved
```bash
python3 -m sidecar.handlers.menu_actions                # frontmost app
python3 -m sidecar.handlers.menu_actions "Safari"        # a named app
```
This isolates whether a problem is in the AppleScript/Accessibility layer
itself versus the `brain.py`/`executor.py` wiring around it — the fastest
way to tell "my Mac setup is wrong" from "Rigel's logic is wrong."

### Watch the fallback path decide, live
```bash
./.venv/bin/python -m sidecar   # run in foreground, don't background it
```
then send a chat message that should trigger a menu action and watch the
console — a `MenuDiscoveryError` caught inside `_menu_action_commands()`
or `_resolve_target_app()` doesn't currently log a `WARNING` line the way
the LLM provider fallback does (see `docs/troubleshooting/llm-brain.md`
for that pattern) — if you need more visibility while debugging, temporarily
add a `logger.debug(...)` call at the relevant `except` in
`sidecar/brain.py`.

### Test the whitelist override directly
```bash
./.venv/bin/python -c "
from sidecar import executor
whitelist = {'click_menu_item': {'TextEdit': {'all': True, 'menu_paths': []}}}
print(executor.is_whitelisted('click_menu_item',
    {'app': 'TextEdit', 'menu_path': ['File', 'Empty Trash']}, whitelist))
# False — 'empty trash' is dangerous, overrides all:true
print(executor.is_whitelisted('click_menu_item',
    {'app': 'TextEdit', 'menu_path': ['Edit', 'Copy']}, whitelist))
# True — not dangerous, all:true applies
"
```

## Resources
- [Feature Doc](../features/menu-actions.md)
- [Architecture Doc](../architecture/menu-actions.md)
- [API Reference](../api/menu-actions-endpoints.md)
- [Proposal / Progress Log](../proposals/menu-actions.md) — the source of
  every live-hardware detail in this guide
