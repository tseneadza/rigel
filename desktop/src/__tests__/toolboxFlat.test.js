import { describe, it, expect } from "vitest";
import {
  FLAT_CX,
  FLAT_CY,
  FLAT_INNER_R,
  FLAT_OUTER_R,
  FLAT_DEFAULT_TILT,
  FLAT_MIN_TILT,
  FLAT_MAX_TILT,
  FLAT_MIN_ZOOM,
  FLAT_MAX_ZOOM,
  ringAngles,
  clampFlatTilt,
  clampFlatZoom,
  flatWheelZoom,
  flatPoint,
} from "../toolboxFlat.js";

const DEG = Math.PI / 180;

describe("2D map geometry (M2 v8.2)", () => {
  it("opens straight down (90°) at zoom 1", () => {
    expect(FLAT_DEFAULT_TILT).toBeCloseTo(90 * DEG, 9);
  });

  it("puts inner and outer states on their rings", () => {
    const at = ringAngles([
      { name: "osa", state: "running" },
      { name: "shell", state: "starting" },
      { name: "git", state: "cold" },
      { name: "mail", state: "not running" },
    ]);
    expect(at.get("osa")).toMatchObject({ ring: "inner", radius: FLAT_INNER_R });
    expect(at.get("shell")).toMatchObject({ ring: "inner", radius: FLAT_INNER_R });
    expect(at.get("git")).toMatchObject({ ring: "outer", radius: FLAT_OUTER_R });
    expect(at.get("mail")).toMatchObject({ ring: "outer", radius: FLAT_OUTER_R });
    // first inner server at the top
    expect(at.get("osa").angle).toBeCloseTo(-Math.PI / 2, 9);
  });

  it("draws a circle when flat and not spun", () => {
    const p = flatPoint(100, 0);
    expect(p.x).toBeCloseTo(FLAT_CX + 100, 9);
    expect(p.y).toBeCloseTo(FLAT_CY, 9);
    const q = flatPoint(100, Math.PI / 2);
    expect(q.y).toBeCloseTo(FLAT_CY + 100, 9);
  });

  it("spins every point around the hub", () => {
    const p = flatPoint(100, 0, { spin: Math.PI / 2 });
    expect(p.x).toBeCloseTo(FLAT_CX, 9);
    expect(p.y).toBeCloseTo(FLAT_CY + 100, 9);
  });

  it("tilt squashes the map vertically and leaves the width alone", () => {
    const p = flatPoint(100, Math.PI / 2, { tilt: 30 * DEG });
    expect(p.y - FLAT_CY).toBeCloseTo(50, 9);
    const q = flatPoint(100, 0, { tilt: 30 * DEG });
    expect(q.x - FLAT_CX).toBeCloseTo(100, 9);
  });

  it("zoom scales the map around the hub", () => {
    const p = flatPoint(100, 0, { zoom: 2 });
    expect(p.x - FLAT_CX).toBeCloseTo(200, 9);
  });

  it("keeps tilt between 20° and 90°", () => {
    expect(clampFlatTilt(120 * DEG)).toBe(FLAT_MAX_TILT);
    expect(clampFlatTilt(5 * DEG)).toBe(FLAT_MIN_TILT);
    expect(FLAT_MIN_TILT).toBeCloseTo(20 * DEG, 9);
  });

  it("keeps zoom between 0.5× and 2.1×", () => {
    expect(clampFlatZoom(9)).toBe(FLAT_MAX_ZOOM);
    expect(clampFlatZoom(0.1)).toBe(FLAT_MIN_ZOOM);
  });

  it("scroll down zooms out, scroll up zooms in, as in 3D", () => {
    expect(flatWheelZoom(1, 100)).toBeLessThan(1);
    expect(flatWheelZoom(1, -100)).toBeGreaterThan(1);
    expect(flatWheelZoom(1, 10000)).toBe(FLAT_MIN_ZOOM);
    expect(flatWheelZoom(1, -10000)).toBe(FLAT_MAX_ZOOM);
  });
});
