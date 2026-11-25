import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import ToolBoxMap, { ringFor, summarise, HINT_2D, HINT_3D, agentLinkEnd } from "../components/ToolBoxMap.jsx";
import { scenePositions, SCENE_INNER_R, SCENE_OUTER_R } from "../toolboxScene.js";
import ToolBoxModeToggle from "../components/ToolBoxModeToggle.jsx";
import { stateTone, resolveMode, readStoredMode, storeMode, MODE_KEY, supports3D } from "../toolboxView.js";

// The 3D scene needs WebGL. jsdom has none, so the renderer is a stub that can be switched on per test.
const webgl = vi.hoisted(() => ({ works: false }));
vi.mock("three", async (importOriginal) => {
  const real = await importOriginal();
  class StubRenderer {
    constructor() {
      if (!webgl.works) throw new Error("WebGL unavailable");
      this.domElement = document.createElement("canvas");
    }
    setPixelRatio() {}
    setSize() {}
    render() {}
    dispose() {}
  }
  return { ...real, WebGLRenderer: StubRenderer };
});

const rows = [
  { name: "notes", state: "running", tools: 6 },
  { name: "shell", state: "starting", tools: 4 },
  { name: "mail", state: "not running", tools: 0, error: "connection refused" },
];

describe("stateTone", () => {
  it("uses ToolBox's labels", () => {
    expect(stateTone("running")).toBe("ok");
    expect(stateTone("starting")).toBe("warn");
    expect(stateTone("stopping")).toBe("warn");
    expect(stateTone("not running")).toBe("bad");
    expect(stateTone("warm")).toBe("neutral");
    // ToolBox's idle label: a neutral grey, not red (Tony, 2026-11-23).
    expect(stateTone("cold")).toBe("neutral");
  });
});

describe("resolveMode", () => {
  it("keeps 2D and 3D when 3D renders", () => {
    expect(resolveMode("2d", true)).toEqual({ mode: "2d", fallbackReason: null });
    expect(resolveMode("3d", true)).toEqual({ mode: "3d", fallbackReason: null });
  });
  it("falls back to 2D with a reason when 3D can't render", () => {
    expect(resolveMode("3d", false)).toEqual({ mode: "2d", fallbackReason: "3D unavailable here, showing 2D." });
  });
});

describe("remembered mode", () => {
  const memory = () => {
    const data = {};
    return { getItem: (k) => (k in data ? data[k] : null), setItem: (k, v) => (data[k] = String(v)) };
  };
  it("defaults to 2D and remembers the last choice", () => {
    const s = memory();
    expect(readStoredMode(s)).toBe("2d");
    storeMode("3d", s);
    expect(s.getItem(MODE_KEY)).toBe("3d");
    expect(readStoredMode(s)).toBe("3d");
  });
});

describe("ToolBoxMap", () => {
  it("draws ToolBox as the hub, servers only (mockup v8.2)", () => {
    render(<ToolBoxMap serverRows={rows} hubState="running" />);
    expect(screen.getByLabelText(/ToolBox running, 3 servers/)).toBeInTheDocument();
    expect(screen.getByText("ToolBox")).toBeInTheDocument();
  });

  it("shows each server's state label and tool count", () => {
    render(<ToolBoxMap serverRows={rows} />);
    expect(screen.getByText("running · 6 tools")).toBeInTheDocument();
    expect(screen.getByText("starting · 4 tools")).toBeInTheDocument();
    expect(screen.getByText("not running · 0 tools")).toBeInTheDocument();
  });

  it("shows the error line only for a server that is not running", () => {
    render(<ToolBoxMap serverRows={rows} />);
    expect(screen.getByText("connection refused")).toBeInTheDocument();
  });

  it("shows ToolBox's cold label in the map", () => {
    render(<ToolBoxMap serverRows={[{ name: "git", state: "cold", tools: 14 }]} />);
    expect(screen.getByText("cold · 14 tools")).toBeInTheDocument();
  });

  it("says so when there is no server detail yet", () => {
    render(<ToolBoxMap serverRows={[]} />);
    expect(screen.getByText("No server detail yet.")).toBeInTheDocument();
  });

  it("shows the fallback reason when 3D was asked for but unavailable", () => {
    render(<ToolBoxMap serverRows={rows} mode="2d" fallbackReason="3D unavailable here, showing 2D." />);
    expect(screen.getByRole("status")).toHaveTextContent("3D unavailable here, showing 2D.");
  });
});

describe("ToolBoxModeToggle", () => {
  it("reports the picked mode and remembers it", () => {
    // Node's built-in localStorage is unavailable in this test run, so use an in-memory stub.
    const data = {};
    vi.stubGlobal("localStorage", {
      getItem: (k) => (k in data ? data[k] : null),
      setItem: (k, v) => (data[k] = String(v)),
      removeItem: (k) => delete data[k],
    });
    const onChange = vi.fn();
    render(<ToolBoxModeToggle mode="2d" onChange={onChange} />);
    expect(screen.getByRole("button", { name: "2D" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "3D" }));
    expect(onChange).toHaveBeenCalledWith("3d");
    expect(data[MODE_KEY]).toBe("3d");
    vi.unstubAllGlobals();
  });
});

describe("two rings by state (M2 v3)", () => {
  it("puts running, starting and stopping on the inner ring", () => {
    expect(ringFor("running")).toBe("inner");
    expect(ringFor("starting")).toBe("inner");
    expect(ringFor("stopping")).toBe("inner");
  });

  it("puts cold and any other state on the outer ring", () => {
    expect(ringFor("cold")).toBe("outer");
    expect(ringFor("not running")).toBe("outer");
    expect(ringFor("unknown")).toBe("outer");
  });

  it("marks each server node with its ring", () => {
    const { container } = render(
      <ToolBoxMap serverRows={[{ name: "git", state: "cold", tools: 14 }, { name: "osa", state: "running", tools: 32 }]} />,
    );
    expect(container.querySelector('[data-state="running"]')).toHaveAttribute("data-ring", "inner");
    expect(container.querySelector('[data-state="cold"]')).toHaveAttribute("data-ring", "outer");
  });
});

describe("summarise (side panel)", () => {
  it("counts states, sums tools, and lists errors", () => {
    const s = summarise([
      { name: "osa", state: "running", tools: 32 },
      { name: "git", state: "cold", tools: 14 },
      { name: "shell", state: "starting", tools: 4 },
      { name: "mail", state: "not running", tools: 0, error: "connection refused" },
    ]);
    expect(s).toMatchObject({ total: 4, running: 1, transition: 1, cold: 1, other: 1, tools: 50 });
    expect(s.errors).toEqual([{ name: "mail", error: "connection refused" }]);
  });

  it("shows the server count and tool total in the side panel", () => {
    render(<ToolBoxMap serverRows={[{ name: "git", state: "cold", tools: 14 }, { name: "osa", state: "running", tools: 32 }]} />);
    expect(screen.getByText("Servers · 2")).toBeInTheDocument();
    expect(screen.getByText(/Tools available/)).toHaveTextContent("46");
  });
});


afterEach(() => {
  webgl.works = false;
  vi.restoreAllMocks();
});

describe("3D scene positions (shared with the 2D rings)", () => {
  const rows = [
    { name: "osa-system", state: "running" },
    { name: "image-tools", state: "starting" },
    { name: "git", state: "cold" },
    { name: "mail", state: "not running" },
  ];

  it("puts running, starting and stopping servers on the inner radius", () => {
    const at = scenePositions(rows);
    for (const name of ["osa-system", "image-tools"]) {
      const p = at.get(name);
      expect(p.ring).toBe("inner");
      expect(Math.hypot(p.x, p.z)).toBeCloseTo(SCENE_INNER_R, 6);
    }
  });

  it("puts cold and other states on the outer radius", () => {
    const at = scenePositions(rows);
    for (const name of ["git", "mail"]) {
      const p = at.get(name);
      expect(p.ring).toBe("outer");
      expect(Math.hypot(p.x, p.z)).toBeCloseTo(SCENE_OUTER_R, 6);
    }
  });

  it("keeps every server on the orbit plane", () => {
    for (const p of scenePositions(rows).values()) expect(p.y).toBe(0);
  });
});

describe("WebGL check", () => {
  it("reports 3D unsupported when no WebGL context can be made", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
    expect(supports3D()).toBe(false);
  });

  it("reports 3D supported when a WebGL context can be made", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({});
    expect(supports3D()).toBe(true);
  });
});

describe("3D mode in the map", () => {
  const rows = [
    { name: "osa-system", state: "running", tools: 21, error: null },
    { name: "git", state: "cold", tools: 10, error: null },
  ];

  it("falls back to the 2D map with the reason when WebGL won't start", () => {
    const { container } = render(<ToolBoxMap serverRows={rows} mode="3d" />);
    expect(screen.getByText("3D unavailable here, showing 2D.")).toBeTruthy();
    expect(container.querySelector(".tb-svg")).toBeTruthy();
    expect(container.querySelector(".tb-scene")).toBeNull();
  });

  it("draws the 3D scene with each server's label when WebGL works", () => {
    webgl.works = true;
    const { container } = render(<ToolBoxMap serverRows={rows} mode="3d" hubState="running" />);
    expect(container.querySelector(".tb-scene")).toBeTruthy();
    expect(container.querySelector(".tb-svg")).toBeNull();
    expect(screen.getByText("osa-system")).toBeTruthy();
    expect(screen.getByText("git")).toBeTruthy();
    expect(screen.getByText("ToolBox")).toBeTruthy();
  });

  it("shows the 2D map in 2D mode and never builds the scene", () => {
    webgl.works = true;
    const { container } = render(<ToolBoxMap serverRows={rows} mode="2d" />);
    expect(container.querySelector(".tb-svg")).toBeTruthy();
    expect(container.querySelector(".tb-scene")).toBeNull();
  });

  it("keeps the side panel summary in 3D", () => {
    webgl.works = true;
    render(<ToolBoxMap serverRows={rows} mode="3d" />);
    expect(screen.getByText("Tools available", { exact: false })).toBeTruthy();
  });
});

describe("2D spin, tilt and zoom (mockup v8.2)", () => {
  const rows2 = [
    { name: "osa", state: "running", tools: 32 },
    { name: "git", state: "cold", tools: 14 },
  ];
  const outerRing = (c) => c.querySelector("ellipse.tb-ring--outer");

  it("opens flat at zoom 1 with the hint and readout in a bar under the map", () => {
    const { container } = render(<ToolBoxMap serverRows={rows2} />);
    const bar = container.querySelector(".tb-map-col > .tb-bar");
    expect(bar).toBeTruthy();
    expect(bar).toHaveTextContent(HINT_2D);
    expect(bar).toHaveTextContent("2D · Tilt 90° · Zoom 1.0×");
    // the bar comes after the map, not inside it
    expect(container.querySelector(".tb-map .tb-bar")).toBeNull();
    expect(outerRing(container).getAttribute("rx")).toBe(outerRing(container).getAttribute("ry"));
  });

  it("puts the Servers panel in its own column, not inside the map column", () => {
    const { container } = render(<ToolBoxMap serverRows={rows2} />);
    const side = container.querySelector(".tb-side");
    expect(side.parentElement).toHaveClass("tb-map-wrap");
    expect(container.querySelector(".tb-map-col .tb-side")).toBeNull();
  });

  it("turns on its own", async () => {
    const { container } = render(<ToolBoxMap serverRows={rows2} />);
    const map = container.querySelector(".tb-map--2d");
    const start = map.dataset.spin;
    await waitFor(() => expect(map.dataset.spin).not.toBe(start));
  });

  it("drag down tips the map back: rings become ovals, readout shows the tilt", () => {
    // jsdom has no PointerEvent; without one the events carry no clientX/clientY.
    if (typeof window.PointerEvent === "undefined") vi.stubGlobal("PointerEvent", class extends MouseEvent {});
    const { container } = render(<ToolBoxMap serverRows={rows2} />);
    const map = container.querySelector(".tb-map--2d");
    act(() => {
      fireEvent.pointerDown(map, { clientX: 100, clientY: 100 });
      fireEvent.pointerMove(window, { clientX: 100, clientY: 250 });
      fireEvent.pointerUp(window);
    });
    expect(container.querySelector(".tb-bar")).toHaveTextContent("2D · Tilt 60° · Zoom 1.0×");
    const ring = outerRing(container);
    expect(Number(ring.getAttribute("ry"))).toBeLessThan(Number(ring.getAttribute("rx")));
  });

  it("scroll zooms in and out within 0.5× to 2.1×", () => {
    const { container } = render(<ToolBoxMap serverRows={rows2} />);
    const map = container.querySelector(".tb-map--2d");
    act(() => {
      fireEvent.wheel(map, { deltaY: -10000 });
    });
    expect(container.querySelector(".tb-bar")).toHaveTextContent("Zoom 2.1×");
    act(() => {
      fireEvent.wheel(map, { deltaY: 10000 });
    });
    expect(container.querySelector(".tb-bar")).toHaveTextContent("Zoom 0.5×");
  });

  it("3D uses the same bar with its own hint", () => {
    webgl.works = true;
    const { container } = render(<ToolBoxMap serverRows={rows2} mode="3d" />);
    const bar = container.querySelector(".tb-map-col > .tb-bar");
    expect(bar).toHaveTextContent(HINT_3D);
    expect(container.querySelector(".tb-scene .tb-bar, .tb-scene-readout, .tb-scene-hint")).toBeNull();
  });
});

describe("pinned agents in 2D (mockup v8.3)", () => {
  const rows3 = [{ name: "osa", state: "running", tools: 32 }];
  const boxPos = (c) => [...c.querySelectorAll(".tb-agent-box rect")].map((r) => `${r.getAttribute("x")},${r.getAttribute("y")}`);

  it("shows Rigel and the other agent at the left edge of the 2D map", () => {
    const { container } = render(<ToolBoxMap serverRows={rows3} />);
    expect(screen.getByText("Rigel")).toBeInTheDocument();
    expect(screen.getByText("other agent")).toBeInTheDocument();
    expect(boxPos(container)).toEqual(["30,200", "30,340"]);
  });

  it("draws the boxes after the servers, so they sit on top", () => {
    const { container } = render(<ToolBoxMap serverRows={rows3} />);
    const svg = container.querySelector(".tb-svg");
    const kids = [...svg.children];
    const lastNode = kids.findLastIndex((k) => k.classList.contains("tb-node"));
    const firstBox = kids.findIndex((k) => k.classList.contains("tb-agent-box"));
    expect(firstBox).toBeGreaterThan(lastNode);
  });

  it("keeps the boxes still when zoomed, and their links follow the hub", () => {
    const { container } = render(<ToolBoxMap serverRows={rows3} />);
    const map = container.querySelector(".tb-map--2d");
    act(() => {
      fireEvent.wheel(map, { deltaY: -10000 });
    });
    expect(boxPos(container)).toEqual(["30,200", "30,340"]);
    const link = container.querySelector('[data-agent-link="Rigel"]');
    const end = agentLinkEnd(0, 2.1);
    expect(Number(link.getAttribute("x2"))).toBeCloseTo(end.x, 6);
    expect(Number(link.getAttribute("y2"))).toBeCloseTo(end.y, 6);
  });

  it("leaves 3D as servers only", () => {
    webgl.works = true;
    render(<ToolBoxMap serverRows={rows3} mode="3d" />);
    expect(screen.queryByText("Rigel")).toBeNull();
    expect(screen.queryByText("other agent")).toBeNull();
  });
});
