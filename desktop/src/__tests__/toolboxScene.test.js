import { describe, it, expect } from "vitest";
import {
  DEFAULT_TILT,
  DEFAULT_DISTANCE,
  MIN_TILT,
  MAX_TILT,
  MIN_DISTANCE,
  MAX_DISTANCE,
  clampElevation,
  clampDistance,
  wheelZoom,
  cameraPosition,
  zoomFactor,
  toDegrees,
} from "../toolboxScene.js";

const DEG = Math.PI / 180;

describe("tilt limits", () => {
  it("starts at 27 degrees, the approved default", () => {
    expect(toDegrees(DEFAULT_TILT)).toBe(27);
  });

  it("stops at flat (85 degrees) and edge-on (5 degrees)", () => {
    expect(toDegrees(clampElevation(120 * DEG))).toBe(85);
    expect(toDegrees(clampElevation(-10 * DEG))).toBe(5);
    expect(clampElevation(MIN_TILT + 0.1)).toBeCloseTo(MIN_TILT + 0.1, 10);
    expect(clampElevation(MAX_TILT - 0.1)).toBeCloseTo(MAX_TILT - 0.1, 10);
  });

  it("puts the camera high when flat and low when edge-on", () => {
    const flat = cameraPosition(MAX_TILT, 10);
    const edge = cameraPosition(MIN_TILT, 10);
    expect(flat.y).toBeGreaterThan(edge.y);
    expect(edge.z).toBeGreaterThan(flat.z);
  });

  it("keeps the camera the same distance from the hub at any tilt", () => {
    for (const deg of [5, 27, 60, 85]) {
      const p = cameraPosition(deg * DEG, DEFAULT_DISTANCE);
      expect(Math.hypot(p.x, p.y, p.z)).toBeCloseTo(DEFAULT_DISTANCE, 6);
    }
  });
});

describe("zoom", () => {
  it("is 1.0x at the default distance", () => {
    expect(zoomFactor(DEFAULT_DISTANCE)).toBeCloseTo(1, 10);
  });

  it("zooms in when scrolling up and out when scrolling down", () => {
    expect(wheelZoom(DEFAULT_DISTANCE, -100)).toBeLessThan(DEFAULT_DISTANCE);
    expect(wheelZoom(DEFAULT_DISTANCE, 100)).toBeGreaterThan(DEFAULT_DISTANCE);
  });

  it("keeps the distance inside the whole-map and close-up range", () => {
    expect(clampDistance(1)).toBe(MIN_DISTANCE);
    expect(clampDistance(100)).toBe(MAX_DISTANCE);
    expect(wheelZoom(MAX_DISTANCE, 10000)).toBe(MAX_DISTANCE);
    expect(wheelZoom(MIN_DISTANCE, -10000)).toBe(MIN_DISTANCE);
  });
});
