# Feature: Orb Minimize / Expand

## Overview
Rigel's window can drop down to *just the orb* — no header, no chat
console, no title bar — and come back to full size again, either
automatically while Rigel is working or by hand via a global hotkey. The
full-size window is a solid black "deep space" background (starfield +
nebula glow behind the orb), never transparent to the desktop.

## Status
- [ ] Planned
- [ ] In Development
- [x] Alpha/Beta
- [ ] Production

## User-Facing Description
- **While Rigel is thinking:** once a request has been in flight for
  2.5 s (`WORKING_MINIMIZE_DELAY_MS`), the header and the whole chat
  console disappear and the actual OS window shrinks to a small square
  holding only the orb. As soon as the reply lands, it restores your exact
  prior window size/position and the full console. Replies that arrive
  faster than that — a voice command round trip, the regex stub — never
  move the window at all; shrinking and restoring for a sub-second wait
  read as the window vanishing and popping back (found live 2026-09-17).
  Recording a spoken command (orange orb) never minimizes either.
- **By hand, anytime:** press **⌘⇧R** to toggle between full size and
  minimized. This is independent of the auto-minimize above — if you
  minimize by hand while Rigel is mid-reply, it stays minimized once the
  reply finishes (your manual choice wins).
- **Look:** the window is always a solid black background with a
  scattered starfield and soft nebula glow — it reads as deep space, not
  a transparent overlay.

## Technical Implementation

### Architecture
```
Cmd+Shift+R (OS-level, via tauri-plugin-global-shortcut)
        │
        ▼
App.jsx: manualMinimize (bool, toggled)  ───┐
                                             ├──▶ minimized = isWorking || manualMinimize
ChatConsole.onBusy / voice transcript ──────┘         │  (isWorking → autoMinimized after 2.5 s)
        │                                             ▼
        │                                  header/console hidden (display:none)
        │                                  orb re-centered + shrunk (CSS)
        ▼                                             │
   orbState "thinking"/"idle"                          ▼
                                        nativeWindow.shrinkToCorner() /
                                        restoreRestingBounds()
                                        (real OS window resize+move)
```

### Key Components
- **Frontend:** `desktop/src/App.jsx` (the `minimized` derivation and the
  two effects below it — this is where auto + manual are unified),
  `desktop/src/hotkey.js` (registers the global shortcut, or a window
  keydown fallback outside Tauri), `desktop/src/nativeWindow.js`
  (`shrinkToCorner`/`restoreRestingBounds` — the actual OS window resize),
  `desktop/src/components/ChatConsole.jsx` (`hidden` prop + scroll
  catch-up, see Known Limitations), `desktop/src/styles.css` (starfield
  background, `.brandline`/`.transcript` glass panels).
- **Native:** `desktop/src-tauri/src/lib.rs` registers
  `tauri_plugin_global_shortcut`; `desktop/src-tauri/capabilities/default.json`
  grants `global-shortcut:allow-register`/`allow-unregister` and
  `core:window:allow-set-size`/`allow-set-position`.
- **Storage:** none — this is entirely transient UI state, never
  persisted. The user's actual resting `orbConfig` (size/position/corner,
  in the `settings` table) is never touched by minimize/expand.

### Data Flow
1. Either `orbState` becomes `"thinking"` (a chat request is in flight)
   or the hotkey flips `manualMinimize` — either sets the derived
   `minimized` boolean to `true`.
2. `App.jsx` re-renders: header is unmounted, the console `<footer>` gets
   `display:none` (but stays mounted — see Known Limitations), and the
   orb's display props switch to a small fixed diameter, centered.
3. A `useEffect` keyed on `minimized` calls `nativeWindow.shrinkToCorner()`,
   which reads the window's current scale factor/size/position and the
   active monitor's bounds, remembers the pre-shrink bounds once, and
   moves+resizes the real OS window to a small square in the monitor's
   bottom-right corner.
4. When `minimized` goes back to `false` (both `isWorking` and
   `manualMinimize` are false), the same effect calls
   `restoreRestingBounds()`, which sets the window back to the exact
   size/position it remembered — not a recomputed guess.

## Configuration
None. The hotkey is hardcoded to `CmdOrCtrl+Shift+R` in `hotkey.js`
(`ACCELERATOR` constant) — change that one string to rebind it.

## Usage Examples

### User Perspective
```
[Rigel full size, black starfield background]
User: "open Chrome and Safari"
  → if the reply takes > 2.5 s: window shrinks to just the orb,
    header/console gone; reply arrives → window restores
  → if the reply is quick: nothing moves
[Press ⌘⇧R anytime] → orb-only, no console
[Press ⌘⇧R again]   → back to full size
```

### Developer Perspective
```js
import { installToggleHotkey } from "./hotkey.js";

useEffect(() => {
  return installToggleHotkey(() => setManualMinimize((m) => !m));
}, []);
```

## Testing
- **Manual Testing Checklist:**
  - [x] Sending a message shrinks the window to orb-only and restores it
        when the reply lands (verified in browser dev preview with an
        artificially delayed `/chat` response).
  - [x] ⌘⇧R toggles minimize/expand while completely idle (no chat
        activity) — verified in browser dev preview via the keydown
        fallback.
  - [x] Manually minimizing mid-request keeps the orb minimized after the
        reply lands, instead of auto-expanding — verified by toggling
        the hotkey during a delayed request and confirming it stayed
        minimized once the reply arrived, then expanded on a second press.
  - [x] A reply that arrives while minimized is not lost — it's in the
        transcript and now correctly scrolled into view once expanded
        (see Known Limitations below for the bug this caught).
  - [ ] The OS-level global shortcut itself (fires while the app isn't
        focused, via `tauri-plugin-global-shortcut`) was **not** verified
        live end-to-end in this environment — see
        [`docs/troubleshooting/orb-minimize.md`](../troubleshooting/orb-minimize.md).

## Known Limitations
- **Scroll catch-up, not truly live:** while the console is
  `display:none`, its scroll container has zero height, so
  `ChatConsole`'s auto-scroll-to-bottom effect can't do anything useful
  when a reply arrives during that time. It's kept mounted (rather than
  unmounted, which would risk a "setState on unmounted component"
  warning if a request finishes after being torn down) and now re-syncs
  scroll position via a `hidden`-keyed effect once shown again — but for
  a split second while still minimized, the DOM has the new message at a
  stale scroll position that nobody sees.
- **Global shortcut isn't verified live in a packaged app** in this
  development environment (this Claude Code session's window lives on a
  macOS Space that couldn't host the bundled `Rigel.app`'s window for
  input testing) — the browser/dev-preview keydown fallback was used
  instead. The Rust/JS wiring, permission strings, and accelerator
  syntax are all correct per the plugin's own docs and match a verified
  passing `cargo check`, but a manual check on a real machine (with the
  app actually unfocused) is worth doing once.
- **Single hardcoded hotkey**, no in-app rebind UI.
- **No affordance to reopen the input while minimized** other than the
  hotkey — no click-to-expand on the mini orb (deliberate, per design
  discussion: the hotkey is the intended mechanism).

## Future Enhancements
- Expose the hotkey combo in Settings instead of hardcoding it.
- A visible indicator (in the minimized orb itself) for "unread reply
  arrived while minimized," since the reply is silent otherwise.

## Related Features
- Builds on the existing resizable/pinnable orb (`ResizeControl.jsx`,
  `orbConfig` in the `settings` table) — minimize/expand is a separate,
  transient overlay on top of that persisted resting state.

## References
- `desktop/src/App.jsx`, `desktop/src/hotkey.js`,
  `desktop/src/nativeWindow.js`, `desktop/src/components/ChatConsole.jsx`
- [`docs/architecture/orb-minimize-state.md`](../architecture/orb-minimize-state.md)
- [`docs/troubleshooting/orb-minimize.md`](../troubleshooting/orb-minimize.md)
