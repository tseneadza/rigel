# Troubleshooting Guide: Orb Minimize / Expand

## Quick Diagnosis

```
Pressing ⌘⇧R does nothing?
│
├─ Running via `npm run dev` in a plain browser tab (not the Tauri app)?
│  → hotkey.js falls back to a window-scoped keydown listener — the
│    BROWSER TAB must be focused, and no other extension/OS binding can
│    already be eating Cmd+Shift+R. See "Hotkey silent in dev preview."
│
├─ Running the real Tauri app, window focused, still nothing?
│  → check the app's console/log for
│    "Failed to register toggle hotkey: ..." — another running app has
│    already claimed Cmd+Shift+R. See "Hotkey silent in the native app."
│
└─ Toggle fires, but the window doesn't actually resize (only the CSS
   orb shrinks, header/console still hidden correctly)?
   → the native resize IPC failed or was denied — see
     "Window doesn't resize" below. The rest of the feature (header/
     console hiding) is pure CSS and unaffected by this.
```

## Common Issues

### Issue: Hotkey silent in dev preview (browser)
**Symptoms:** `npm run dev` open in a browser tab, ⌘⇧R does nothing.

**Diagnosis:**
- Click into the Rigel tab first — `hotkey.js`'s fallback path is a
  plain `window.addEventListener("keydown", ...)`, which only fires
  while that window/tab has focus (there's no OS-level fallback outside
  Tauri; the global-shortcut plugin literally cannot run in a browser).
- Check whether the browser or an extension already intercepts
  Cmd+Shift+R (some browsers/extensions use it for "hard reload" or a
  custom action) — it may never reach the page's `keydown` listener.

**Solutions:**
- Click the Rigel tab/window before pressing the combo.
- If your browser has bound Cmd+Shift+R itself, test with the real
  Tauri app instead (`npx tauri dev` from `desktop/`) — the OS-level
  global shortcut doesn't go through the browser at all.

### Issue: Hotkey silent in the native app
**Symptoms:** Running the actual Tauri app; ⌘⇧R does nothing, focused or
not.

**Diagnosis:** Check the app's log (stdout in `npx tauri dev`, or
Console.app for a bundled `.app`) for:
```
Failed to register toggle hotkey: ...
```
This means `register()` rejected — almost always because another
running application has already claimed `CmdOrCtrl+Shift+R` as its own
global shortcut (only one process can own a given combo at a time on
macOS).

**Solutions:**
1. Quit or rebind whatever else has claimed it, or
2. Change Rigel's own binding: edit the `ACCELERATOR` constant in
   `desktop/src/hotkey.js` to something free on your machine, e.g.
   `"Alt+Shift+R"`. Accelerator syntax reference: modifiers are
   `CmdOrCtrl`/`Cmd`/`Ctrl`/`Alt`(or `Option`)/`Shift`/`Super`, joined
   with `+`, e.g. `"CmdOrCtrl+Shift+R"`.

> **Not an Accessibility/Input Monitoring issue:** unlike some
> global-hotkey approaches, `tauri-plugin-global-shortcut` uses macOS's
> Carbon `RegisterEventHotKey` API under the hood for ordinary
> modifier+key combos, which does **not** require granting Rigel
> Accessibility or Input Monitoring permission. If macOS is prompting
> for either of those, it's for something else in the app, not this
> hotkey.

### Issue: Window doesn't resize (but header/console still hide correctly)
**Symptoms:** Pressing ⌘⇧R correctly hides the header/console and shrinks
the *orb itself* (CSS), but the actual OS window stays full size.

**Diagnosis:**
- Check `desktop/src-tauri/capabilities/default.json` still grants
  `core:window:allow-set-size` and `core:window:allow-set-position` —
  removing either silently makes `nativeWindow.js`'s calls reject (it
  doesn't `.catch`/log, by design — see
  [`docs/architecture/orb-minimize-state.md`](../architecture/orb-minimize-state.md)'s
  Error Handling section on why that's intentional and low-risk).
- Confirm you're actually running the Tauri app, not the plain browser
  preview — `nativeWindow.js` no-ops entirely outside a Tauri webview
  (`isTauri()` check), so the browser preview can only ever show the
  CSS-level shrink, never the real window resize. This is expected, not
  a bug.

**Solutions:**
- Re-add the two `core:window:allow-*` permissions if they were removed.
- Test in the real Tauri app (`npx tauri dev`), not the browser.

### Issue: A reply that arrived while minimized seems to be missing
**Symptoms:** Send a message, ⌘⇧R to check something else, come back and
expand — the transcript looks like it's missing the newest exchange.

**Diagnosis:** It's almost certainly still there, just scrolled out of
view — this was a real bug (auto-scroll silently no-ops while the
console is `display:none`), fixed by re-syncing scroll position when
the console becomes visible again. Scroll the transcript panel down
manually to confirm, or check the sidecar directly:
```bash
curl -s http://127.0.0.1:5140/api/rigel/logs | python3 -m json.tool
```
If the message is in the sidecar's log but the transcript still looks
stuck after expanding, that's a regression of the fix in
`ChatConsole.jsx` (`hidden`-prop effect) — worth re-checking against
[`docs/architecture/orb-minimize-state.md`](../architecture/orb-minimize-state.md).

## Advanced Debugging

### Confirm which mechanism is actually active
```js
// In the app's devtools console:
"__TAURI_INTERNALS__" in window
// true  → OS-level global shortcut via tauri-plugin-global-shortcut
// false → browser/dev-preview keydown fallback (window must have focus)
```

### Watch the minimize state live
```js
// devtools console, while the app is running:
document.querySelector(".rigel-orb").getAttribute("data-minimized")
// "true" while minimized (either automatically or by hand)
```

## Resources
- [Feature doc](../features/orb-minimize.md)
- [Architecture doc](../architecture/orb-minimize-state.md)
- [`tauri-plugin-global-shortcut` docs](https://v2.tauri.app/plugin/global-shortcut/)
