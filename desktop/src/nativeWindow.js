/**
 * Native window sync — shrinks the actual OS window (not just the CSS orb)
 * down to a small corner square while Rigel is working, and restores it
 * afterward. No-ops outside a Tauri webview (plain browser/dev preview) so
 * the rest of the app doesn't need to guard every call.
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

// Keep a window fully on-screen even for an extreme corner/custom/dragged position.
function clampToScreen(x, y, width, height, screen) {
  return {
    x: Math.min(Math.max(x, screen.position.x), screen.position.x + screen.size.width - width),
    y: Math.min(Math.max(y, screen.position.y), screen.position.y + screen.size.height - height),
  };
}

// Where to park the shrunk window on the monitor. "center" and the four
// corners match Settings → Orb's position picker; "custom" places it by
// percentage of the screen (the window is centered on that point), matching
// how a free-drag (see endWindowDrag below) reports its result.
function cornerPosition({ corner, xPct, yPct, screen, width, height, margin }) {
  if (corner === "custom" && xPct != null && yPct != null) {
    return {
      x: screen.position.x + Math.round((xPct / 100) * screen.size.width) - Math.round(width / 2),
      y: screen.position.y + Math.round((yPct / 100) * screen.size.height) - Math.round(height / 2),
    };
  }
  if (corner === "center") {
    return {
      x: screen.position.x + Math.round((screen.size.width - width) / 2),
      y: screen.position.y + Math.round((screen.size.height - height) / 2),
    };
  }
  const atLeft = corner === "top-left" || corner === "bottom-left";
  const atTop = corner === "top-left" || corner === "top-right";
  return {
    x: atLeft ? screen.position.x + margin : screen.position.x + screen.size.width - width - margin,
    y: atTop ? screen.position.y + margin : screen.position.y + screen.size.height - height - margin,
  };
}

export async function shrinkToCorner({
  widthPx,
  heightPx,
  marginPx = 24,
  corner = "bottom-right",
  xPct = null,
  yPct = null,
}) {
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
  const target = cornerPosition({ corner, xPct, yPct, screen, width, height, margin });
  const { x, y } = clampToScreen(target.x, target.y, width, height, screen);
  await win.setSize(new PhysicalSize(width, height));
  await win.setPosition(new PhysicalPosition(x, y));
  // No drop shadow while the window is a transparent square holding only
  // the orb — macOS would otherwise outline the invisible window edge.
  await win.setShadow(false).catch(() => {});
}

export async function restoreRestingBounds() {
  const win = await getCurrentWindow();
  if (!win || !restingBounds) return;
  await win.setSize(restingBounds.size);
  await win.setPosition(restingBounds.position);
  await win.setShadow(true).catch(() => {});
  restingBounds = null;
}

// ── live drag of the minimized window ───────────────────────────────────
//
// While minimized, the whole shrunk window follows the cursor as the user
// drags the orb — the same way dragging a normal titlebar would — rather
// than just nudging a CSS position inside a window that never moves.

let dragSession = null; // { win, scaleFactor, startWindowX/Y, startScreenX/Y, width, height, screen }
let pendingDragPoint = null;
let dragTail = Promise.resolve();
// dragWindowTo/endWindowDrag can be called before this async setup finishes
// (a fast click, or a move right after pointerdown) — they await this so
// they never race ahead of dragSession being populated.
let dragSetup = Promise.resolve();

export function beginWindowDrag(screenX, screenY) {
  dragSession = null;
  dragSetup = (async () => {
    const win = await getCurrentWindow();
    if (!win) return;
    const { currentMonitor } = await import("@tauri-apps/api/window");
    const [scaleFactor, outerPosition, outerSize, screen] = await Promise.all([
      win.scaleFactor(),
      win.outerPosition(),
      win.outerSize(),
      currentMonitor(),
    ]);
    if (!screen) return;
    dragSession = {
      win,
      scaleFactor,
      startWindowX: outerPosition.x,
      startWindowY: outerPosition.y,
      startScreenX: screenX,
      startScreenY: screenY,
      width: outerSize.width,
      height: outerSize.height,
      screen,
    };
  })();
}

async function applyDragPoint(screenX, screenY) {
  const s = dragSession;
  if (!s) return;
  const { PhysicalPosition } = await import("@tauri-apps/api/dpi");
  // screenX/Y are logical (CSS) pixels, like the widthPx/heightPx callers
  // pass elsewhere in this file — scale to physical pixels the same way.
  const dx = Math.round((screenX - s.startScreenX) * s.scaleFactor);
  const dy = Math.round((screenY - s.startScreenY) * s.scaleFactor);
  const { x, y } = clampToScreen(s.startWindowX + dx, s.startWindowY + dy, s.width, s.height, s.screen);
  await s.win.setPosition(new PhysicalPosition(x, y));
}

// Pointer events fire faster than a setPosition IPC round trip resolves, so
// this coalesces bursts down to "apply only the latest point queued" rather
// than piling up one in-flight setPosition call per pointermove.
export function dragWindowTo(screenX, screenY) {
  pendingDragPoint = { screenX, screenY };
  dragTail = dragTail.then(() => dragSetup).then(() => {
    if (!dragSession || !pendingDragPoint) return;
    const { screenX: sx, screenY: sy } = pendingDragPoint;
    pendingDragPoint = null;
    return applyDragPoint(sx, sy);
  });
}

// Ends the drag and reports where the window ended up, as a percentage of
// the screen (the window's center point) — the same shape Settings → Orb's
// "custom" position already persists, so it's reapplied by shrinkToCorner
// next time the orb minimizes. Returns null for a plain click (no real
// movement), so that doesn't silently overwrite a named corner with "custom".
export async function endWindowDrag() {
  await dragSetup;
  const s = dragSession;
  if (!s) return null;
  await dragTail;
  const pos = await s.win.outerPosition();
  dragSession = null;
  const movedPx = Math.abs(pos.x - s.startWindowX) + Math.abs(pos.y - s.startWindowY);
  if (movedPx < 2 * s.scaleFactor) return null;
  const clampPct = (v) => Math.min(100, Math.max(0, v));
  return {
    xPct: clampPct(((pos.x - s.screen.position.x + s.width / 2) / s.screen.size.width) * 100),
    yPct: clampPct(((pos.y - s.screen.position.y + s.height / 2) / s.screen.size.height) * 100),
  };
}
