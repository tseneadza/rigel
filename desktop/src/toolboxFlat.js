/**
 * 2D Toolbox map geometry (mockup M2 v8.2). Pure functions, so they are
 * testable without rendering.
 *
 * The 2D map stays a flat drawing: tilt squashes it vertically (the rings
 * become ovals, the labels stay upright) and zoom scales it around the hub.
 * Drag and idle-spin rates are the same as the 3D scene's.
 */
import { ringFor } from "./toolboxView.js";

const DEG = Math.PI / 180;

export const FLAT_WIDTH = 1000;
export const FLAT_HEIGHT = 600;
export const FLAT_CX = FLAT_WIDTH / 2;
export const FLAT_CY = FLAT_HEIGHT / 2;
export const FLAT_INNER_R = 150;
export const FLAT_OUTER_R = 255;
export const FLAT_HUB_R = 38;
export const FLAT_NODE_R = 13;

/** 90° looks straight down (flat, the default); 20° is tipped well back. */
export const FLAT_DEFAULT_TILT = 90 * DEG;
export const FLAT_MIN_TILT = 20 * DEG;
export const FLAT_MAX_TILT = 90 * DEG;

/** Same zoom range as 3D (about 0.5× to 2.1×). */
export const FLAT_MIN_ZOOM = 0.5;
export const FLAT_MAX_ZOOM = 2.1;
const WHEEL_RATE = 0.0015;

/**
 * Ring and angle for every row. Running, starting and stopping sit on the
 * inner ring; everything else on the outer ring, half a step offset so its
 * labels don't sit on the inner ring's spokes. Spread evenly from the top.
 */
export function ringAngles(rows) {
  const inner = rows.filter((r) => ringFor(r.state) === "inner");
  const outer = rows.filter((r) => ringFor(r.state) === "outer");
  const at = new Map();
  const spread = (list, ring, radius, offset) =>
    list.forEach((row, i) => {
      const angle = -Math.PI / 2 + offset + (i * 2 * Math.PI) / Math.max(list.length, 1);
      at.set(row.name, { ring, radius, angle });
    });
  spread(inner, "inner", FLAT_INNER_R, 0);
  spread(outer, "outer", FLAT_OUTER_R, Math.PI / Math.max(outer.length, 1));
  return at;
}

export function clampFlatTilt(tilt) {
  return Math.min(FLAT_MAX_TILT, Math.max(FLAT_MIN_TILT, tilt));
}

export function clampFlatZoom(zoom) {
  return Math.min(FLAT_MAX_ZOOM, Math.max(FLAT_MIN_ZOOM, zoom));
}

/** Scroll down zooms out, scroll up zooms in (same direction as 3D). */
export function flatWheelZoom(zoom, deltaY) {
  return clampFlatZoom(zoom * Math.exp(-deltaY * WHEEL_RATE));
}

/** Screen point (viewBox units) for a ring position under the current spin, tilt and zoom. */
export function flatPoint(radius, angle, { spin = 0, tilt = FLAT_DEFAULT_TILT, zoom = 1 } = {}) {
  const a = angle + spin;
  return {
    x: FLAT_CX + zoom * radius * Math.cos(a),
    y: FLAT_CY + zoom * radius * Math.sin(a) * Math.sin(tilt),
  };
}
