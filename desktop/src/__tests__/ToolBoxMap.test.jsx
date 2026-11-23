import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ToolBoxMap, { ringFor, summarise } from "../components/ToolBoxMap.jsx";
import ToolBoxModeToggle from "../components/ToolBoxModeToggle.jsx";
import { stateTone, resolveMode, readStoredMode, storeMode, MODE_KEY } from "../toolboxView.js";

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
  it("draws ToolBox as the hub with Rigel at the edge", () => {
    render(<ToolBoxMap serverRows={rows} hubState="running" />);
    expect(screen.getByLabelText(/ToolBox running, 3 servers/)).toBeInTheDocument();
    expect(screen.getByText("ToolBox")).toBeInTheDocument();
    expect(screen.getByText("Rigel")).toBeInTheDocument();
    expect(screen.getByText("other agent")).toBeInTheDocument();
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
