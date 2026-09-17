# Architecture: Orb Minimize/Expand State

## Purpose
Drives whether Rigel shows its full window (header + orb + chat console)
or just the orb, and keeps the real OS window in sync with that choice —
from two independent triggers (an in-flight chat request, and a global
hotkey) that must not fight each other.

## High-Level Diagram
```
┌─────────────────────┐        ┌──────────────────────┐
│  ChatConsole.onBusy  │        │  hotkey.js (⌘⇧R)      │
│  (request lifecycle) │        │  toggle callback      │
└──────────┬───────────┘        └──────────┬───────────┘
           │ orbState                      │ manualMinimize
           │ "thinking"/"idle"             │ (flips on each press)
           ▼                               ▼
        isWorking ────────────OR──────────► minimized (derived, App.jsx)
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    ▼                          ▼                          ▼
        header unmounted           console display:none          orb re-centered
        (JSX conditional)          (stays mounted — see below)   + shrunk (CSS props)
                                               │
                                               ▼
                              nativeWindow.shrinkToCorner() /
                              restoreRestingBounds()
                              (Tauri window.setSize/setPosition)
```

## Components

### `App.jsx` — `minimized` derivation
- **Language:** JavaScript (React)
- **Location:** `desktop/src/App.jsx`
- **Purpose:** Single source of truth for whether Rigel is minimized,
  combining two independent signals with OR:
  `const minimized = autoMinimized || manualMinimize;` where
  `autoMinimized` follows `isWorking` (`orbState === "thinking"`) only
  after it has been continuously true for `WORKING_MINIMIZE_DELAY_MS`
  (2.5 s) — a debounce added once live voice testing showed sub-second
  round trips making the window flicker.
- **Why OR, not a single state machine:** `isWorking` is *transient* and
  owned by the request lifecycle (`ChatConsole.onBusy`); `manualMinimize`
  is a *sticky* user choice toggled by the hotkey. OR means: a request
  auto-minimizes regardless of the manual flag, and — critically — if the
  user manually minimized before or during a request, the manual choice
  outlives the request (finishing the request alone can't force an
  expand the user didn't ask for). Verified by manually minimizing
  mid-request and confirming it stayed minimized once the reply landed.
- **Public Interface:** not exported — internal to `App`'s render.

### `hotkey.js` — global toggle
- **Language:** JavaScript
- **Location:** `desktop/src/hotkey.js`
- **Purpose:** Registers `CmdOrCtrl+Shift+R` as a true OS-level global
  shortcut via `@tauri-apps/plugin-global-shortcut` (fires even when
  Rigel isn't focused). Outside a Tauri webview — i.e. the Vite dev
  server / browser preview, where that plugin can't function — falls
  back to a plain `window.addEventListener("keydown", ...)` for the same
  combo, active only while the window has focus.
- **Dependencies:** `@tauri-apps/plugin-global-shortcut` (JS) +
  `tauri-plugin-global-shortcut` (Rust, registered in `lib.rs`) +
  `global-shortcut:allow-register`/`allow-unregister` capability
  permissions.
- **Public Interface:** `installToggleHotkey(onToggle): () => void`
  (returns an unregister/cleanup function, matching the
  `useEffect`-with-cleanup convention already used by `nativeWindow.js`).

### `nativeWindow.js` — real window resize
- **Language:** JavaScript
- **Location:** `desktop/src/nativeWindow.js`
- **Purpose:** `shrinkToCorner({widthPx, heightPx, marginPx})` reads the
  current window's scale factor, size, and position plus the active
  monitor's bounds, remembers the pre-shrink bounds *once* (guarded by
  `if (!restingBounds)` so a second shrink call while already shrunk
  doesn't overwrite the real resting size with the shrunk one), then
  computes a physical-pixel size/position anchored to the monitor's
  bottom-right corner. `restoreRestingBounds()` sets the window back to
  exactly what was remembered and clears it.
- **Dependencies:** `@tauri-apps/api/window` (`getCurrentWindow`,
  `currentMonitor`), `@tauri-apps/api/dpi` (`PhysicalSize`,
  `PhysicalPosition`). No-ops entirely outside Tauri via an `isTauri()`
  guard, so the dev/browser preview just skips real window resize and
  only exercises the CSS-level minimize.

## Data Flow

### Primary Flow: minimize while working
1. `ChatConsole.submit()` calls `onBusy(true)` synchronously before
   `await`-ing the sidecar request → `App` sets `orbState = "thinking"`.
2. `isWorking` becomes `true` → `minimized` becomes `true` → re-render:
   header unmounted, footer gets `display:none`, orb's display props
   switch to the small fixed diameter.
3. A `useEffect` keyed on `[minimized]` fires `shrinkToCorner(...)`.
4. Sidecar responds → `ChatConsole`'s `finally` block calls `onBusy(false)`
   → `orbState = "idle"` → if `manualMinimize` is also `false`,
   `minimized` becomes `false` → the same effect fires
   `restoreRestingBounds()`.

### Secondary Flow: manual toggle
1. Hotkey fires (native, OS-level — or the keydown fallback) →
   `setManualMinimize(m => !m)`.
2. Same `minimized` derivation and effect as above; independent of
   whatever `orbState` currently is.

### Error Handling
- `shrinkToCorner`/`restoreRestingBounds` are fire-and-forget from
  `App.jsx`'s effect (no `.catch`) — a failure here (e.g. the OS denies
  the resize) degrades to the window staying at its current size while
  the CSS-level minimize (header/console hidden, orb small) still
  applies correctly. Nothing in the chat path depends on the native
  resize succeeding.

## Concurrency & State Management
- `ChatConsole` is kept **mounted** (not conditionally rendered) while
  minimized, specifically so an in-flight request's `finally` block
  (`setSending(false)`, `onBusy(false)`) never runs against an unmounted
  component — which would otherwise risk React's "Cannot update state of
  an unmounted component" warning/leak. It's hidden purely via
  `style={{ display: "none" }}` from the parent.
- **Real bug this caused, and the fix:** while `display:none`, the
  transcript `<div>` has `scrollHeight === 0`, so the existing
  `useEffect(() => { el.scrollTop = el.scrollHeight }, [turns])`
  auto-scroll is a no-op — a reply arriving during that window lands in
  the DOM at the wrong scroll position, invisible once the console is
  shown again. Fixed with a second effect in `ChatConsole.jsx` keyed on
  a new `hidden` prop: `useEffect(() => { if (!hidden) el.scrollTop =
  el.scrollHeight }, [hidden])` — re-syncs scroll position the moment it
  becomes visible again. Caught and verified via the same delayed-fetch
  browser test used for the auto-minimize behavior itself.

## Performance Characteristics
- All state changes are synchronous React state + a handful of async
  Tauri IPC calls (`setSize`/`setPosition`) — no measurable latency
  concern; the visible "shrink" animation is CSS transition, not tied to
  the native resize's completion.

## External Dependencies
| Dependency | Version | Purpose | License |
|-----------|---------|---------|---------|
| `@tauri-apps/plugin-global-shortcut` | ^2.3.2 | OS-level hotkey registration | MIT/Apache-2.0 |
| `tauri-plugin-global-shortcut` (Rust) | 2.x | Same, native side | MIT/Apache-2.0 |
| `@tauri-apps/api` (`window`, `dpi`) | ^2.11.1 | Real window resize/position | MIT/Apache-2.0 |

## Alternative Approaches Considered
- **Transparent, click-through window (rejected):** an earlier pass made
  the whole window transparent (`transparent: true` +
  `macOSPrivateApi: true`) with `setIgnoreCursorEvents` toggled via a
  `mousemove` hit-test, so clicks would fall through to the desktop
  outside the header/orb/console. Explicitly rejected per design
  feedback: the full-size window should look like solid "outer space"
  (opaque black + starfield), never see-through to the desktop, and the
  minimized view should show *only* the orb rather than a transparent
  gap where the console used to be. Reverted in favor of the current
  opaque-always design; `nativeWindow.js` dropped
  `setClickThrough`/`installClickThroughTracking` entirely, and
  `tauri.conf.json` dropped `transparent`/`macOSPrivateApi` along with
  the matching Cargo feature flag and capability permission.
- **Unmounting `ChatConsole` while minimized (rejected):** would avoid
  needing the `hidden` prop/scroll-catch-up fix, but risks tearing down
  the component mid-request (see Concurrency section above) — the
  `finally` block's `onBusy(false)` call is on the *parent*, so it's
  safe either way, but `setSending(false)` is the *child's own* state
  and would warn/leak if the child were unmounted first. `display:none`
  avoids that class of bug entirely at the cost of the scroll quirk,
  which was straightforward to fix.

## Future Improvements
- Configurable hotkey (currently a hardcoded string constant).
- A ResizeObserver-based scroll fix in `ChatConsole` instead of the
  explicit `hidden` prop, so any future display-toggle mechanism (not
  just this one) gets the catch-up behavior for free.

## Testing Strategy
- **Manual, browser dev-preview:** all state-machine behavior (auto
  minimize on request, hotkey toggle, manual-overrides-auto persistence,
  scroll catch-up) verified live via `npm run dev` + the Chrome-based
  browser tool, using a monkey-patched `fetch` to add artificial delay to
  `/chat` so the transient "thinking" state could actually be observed.
- **Native window resize math:** verified via a mocked Node test
  (`nativeWindow.js` copied into an isolated dir with fake
  `@tauri-apps/api/window` and `@tauri-apps/api/dpi` modules) asserting
  the exact scaled size/position sent to `setSize`/`setPosition`, and
  that `restoreRestingBounds` restores the *original* remembered bounds
  rather than recomputing them.
- **Not verified:** the OS-level global shortcut firing while the
  bundled `.app` is unfocused. This Claude Code session's own window
  lives in a macOS Space that couldn't host the bundled `Rigel.app`'s
  window for input-injection testing (confirmed via the sidecar's own
  turn log never showing test messages sent through `computer-use`
  input-injection tools). The Rust/JS wiring passed `cargo check` and
  matches the plugin's documented API exactly; a real manual check is
  still worth doing.

## References
- [`docs/features/orb-minimize.md`](../features/orb-minimize.md)
- [`docs/troubleshooting/orb-minimize.md`](../troubleshooting/orb-minimize.md)
- `desktop/src/App.jsx`, `desktop/src/hotkey.js`,
  `desktop/src/nativeWindow.js`, `desktop/src/components/ChatConsole.jsx`
