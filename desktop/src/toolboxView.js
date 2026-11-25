/**
 * Toolbox view helpers (mockup M2 v2). Pure functions, so they are testable
 * without rendering.
 *
 * Server states use ToolBox's own labels exactly: running, starting,
 * stopping, not running. Anything else is shown as-is with a neutral tone.
 */

export const MODE_KEY = "rigel.toolboxView";

/** Colour family for a ToolBox state label. */
export function stateTone(state) {
  if (state === "running") return "ok";
  if (state === "starting" || state === "stopping") return "warn";
  if (state === "not running") return "bad";
  return "neutral";
}

/** Whether this runtime can start WebGL (needed for the 3D scene). */
export function supports3D() {
  try {
    const c = document.createElement("canvas");
    return Boolean(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

/** ToolBox states that sit on the inner ring. Every other state sits on the outer ring. */
const INNER_STATES = new Set(["running", "starting", "stopping"]);
export function ringFor(state) {
  return INNER_STATES.has(state) ? "inner" : "outer";
}

/** Remembered choice from localStorage: "2d" (default) or "3d". */
export function readStoredMode(storage = globalThis.localStorage) {
  try {
    return storage?.getItem(MODE_KEY) === "3d" ? "3d" : "2d";
  } catch {
    return "2d";
  }
}

export function storeMode(mode, storage = globalThis.localStorage) {
  try {
    storage?.setItem(MODE_KEY, mode === "3d" ? "3d" : "2d");
  } catch {
    /* storage unavailable: the choice just won't persist */
  }
}

/**
 * What to show for a requested mode. The remembered choice is kept even when
 * 3D can't render; only the displayed mode falls back to 2D (mockup v2).
 */
export function resolveMode(requested, supported) {
  if (requested === "3d" && !supported) {
    return { mode: "2d", fallbackReason: "3D unavailable here, showing 2D." };
  }
  return { mode: requested === "3d" ? "3d" : "2d", fallbackReason: null };
}
