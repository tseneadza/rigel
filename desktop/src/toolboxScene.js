import { ringFor } from "./toolboxView.js";

const DEG = Math.PI / 180;

/** Scene units for the 3D orbit. */
export const SCENE_INNER_R = 2.2;
export const SCENE_OUTER_R = 3.6;

/** Camera tilt above the orbit plane, in radians. Flat is high, edge-on is low. */
export const DEFAULT_TILT = 27 * DEG;
export const MIN_TILT = 5 * DEG;
export const MAX_TILT = 85 * DEG;
/** Radians of tilt per pixel of vertical drag (drag up tilts toward flat). */
export const TILT_PER_PX = 0.2 * DEG;
/** Radians of spin per pixel of horizontal drag. */
export const SPIN_PER_PX = 0.008;
export const IDLE_SPIN = 0.002;

/** Camera distance from the hub. Zoom 1.0x is the default distance. */
export const DEFAULT_DISTANCE = 9.5;
export const MIN_DISTANCE = 4.5;
export const MAX_DISTANCE = 20;

/**
 * Position of each server on the orbit plane (y = 0), spread evenly around
 * each ring. Inner-ring servers start at angle 0; outer-ring servers are
 * offset half a step so the two rings do not line up.
 * Returns Map name -> { x, y, z, ring }.
 */
export function scenePositions(rows) {
  const inner = rows.filter((r) => ringFor(r.state) === "inner");
  const outer = rows.filter((r) => ringFor(r.state) === "outer");
  const at = new Map();
  const place = (list, radius, offset, ring) =>
    list.forEach((row, i) => {
      const a = offset + (i * 2 * Math.PI) / Math.max(list.length, 1);
      at.set(row.name, { x: radius * Math.cos(a), y: 0, z: radius * Math.sin(a), ring });
    });
  place(inner, SCENE_INNER_R, 0, "inner");
  place(outer, SCENE_OUTER_R, Math.PI / Math.max(outer.length, 1), "outer");
  return at;
}

export function clampElevation(elevation) {
  return Math.min(MAX_TILT, Math.max(MIN_TILT, elevation));
}

export function clampDistance(distance) {
  return Math.min(MAX_DISTANCE, Math.max(MIN_DISTANCE, distance));
}

/** Scroll down (deltaY > 0) zooms out; scroll up zooms in. */
export function wheelZoom(distance, deltaY) {
  return clampDistance(distance * Math.exp(deltaY * 0.0015));
}

/** Camera position looking at the hub from the given tilt and distance. */
export function cameraPosition(elevation, distance) {
  return { x: 0, y: distance * Math.sin(elevation), z: distance * Math.cos(elevation) };
}

export function zoomFactor(distance) {
  return DEFAULT_DISTANCE / distance;
}

export function toDegrees(radians) {
  return Math.round(radians / DEG);
}
