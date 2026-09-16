/**
 * Native window sync — makes the actual OS window (not just the CSS orb)
 * borderless, transparent, click-through, and shrink-to-fit while Rigel is
 * working. No-ops outside a Tauri webview (plain browser/dev preview) so the
 * rest of the app doesn't need to guard every call.
 */
const isTauri = () => typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

let currentWindowPromise = null;
async function getCurrentWindow() {
  if (!isTauri()) return null;
  if (!currentWindowPromise) {
    currentWindowPromise = import("@tauri-apps/api/window").then((m) => m.getCurrentWindow());
  }
  return currentWindowPromise;
}

// The window size/position Rigel occupied before it last shrank to work —
// restored once the reply lands.
let restingBounds = null;

export async function shrinkToCorner({ widthPx, heightPx, marginPx = 24 }) {
  const win = await getCurrentWindow();
  if (!win) return;
  const { currentMonitor } = await import("@tauri-apps/api/window");
  const [scaleFactor, outerSize, outerPosition, screen] = await Promise.all([
    win.scaleFactor(),
    win.outerSize(),
    win.outerPosition(),
    currentMonitor(),
  ]);
  if (!restingBounds) {
    restingBounds = { size: outerSize, position: outerPosition };
  }
  if (!screen) return;
  const { PhysicalSize, PhysicalPosition } = await import("@tauri-apps/api/dpi");
  const width = Math.round(widthPx * scaleFactor);
  const height = Math.round(heightPx * scaleFactor);
  const margin = Math.round(marginPx * scaleFactor);
  const x = screen.position.x + screen.size.width - width - margin;
  const y = screen.position.y + screen.size.height - height - margin;
  await win.setSize(new PhysicalSize(width, height));
  await win.setPosition(new PhysicalPosition(x, y));
}

export async function restoreRestingBounds() {
  const win = await getCurrentWindow();
  if (!win || !restingBounds) return;
  await win.setSize(restingBounds.size);
  await win.setPosition(restingBounds.position);
  restingBounds = null;
}

let ignoringCursor = false;
export async function setClickThrough(shouldIgnore) {
  if (shouldIgnore === ignoringCursor) return;
  const win = await getCurrentWindow();
  if (!win) return;
  ignoringCursor = shouldIgnore;
  await win.setIgnoreCursorEvents(shouldIgnore);
}

// Elements the mouse must be able to click normally; everywhere else on the
// (now-transparent) window is desktop showing through, so we let clicks fall
// through to whatever's behind Rigel.
const INTERACTIVE_SELECTOR = ".brandline, .rigel-orb, .console, .settings-overlay";

export function installClickThroughTracking({ enabled }) {
  if (!isTauri()) return () => {};

  function handleMove(e) {
    if (!enabled()) {
      setClickThrough(false);
      return;
    }
    const overInteractive = e.target.closest(INTERACTIVE_SELECTOR) != null;
    setClickThrough(!overInteractive);
  }

  window.addEventListener("mousemove", handleMove);
  return () => window.removeEventListener("mousemove", handleMove);
}
