import { useEffect, useRef, useState } from "react";
import { stateTone, ringFor } from "../toolboxView.js";
import { IDLE_SPIN, SPIN_PER_PX, TILT_PER_PX, toDegrees } from "../toolboxScene.js";
import {
  FLAT_WIDTH,
  FLAT_HEIGHT,
  FLAT_CX,
  FLAT_CY,
  FLAT_INNER_R,
  FLAT_OUTER_R,
  FLAT_HUB_R,
  FLAT_NODE_R,
  FLAT_DEFAULT_TILT,
  ringAngles,
  clampFlatTilt,
  flatWheelZoom,
  flatPoint,
} from "../toolboxFlat.js";
import ToolBoxScene from "./ToolBoxScene.jsx";

/**
 * ToolBox map (mockup M2 v8.2). ToolBox is the hub. Running, starting and
 * stopping servers sit on the inner ring; cold and other states sit on the
 * outer ring. Read-only.
 *
 * 2D is a flat SVG map that turns on its own; drag left/right spins it, drag
 * up/down tilts it (rings become ovals, labels stay upright), scroll zooms.
 * 3D is a WebGL (three.js) scene with the same rings and controls.
 *
 * Rigel and other agents are pinned at the left edge of the 2D map (v8.3);
 * 3D shows servers only.
 *
 * Layout: the map column (map, then a bar with the hint and readout) and the
 * Servers column beside it. Nothing sits on top of the map.
 *
 * `serverRows` is [{ name, state, tools, error? }] (state is ToolBox's own
 * label). `mode` is the displayed mode ("2d" | "3d"). `fallbackReason` is shown
 * when 3D was asked for but can't render here.
 */
export { ringFor };

export const HINT_2D = "Turns on its own. Drag left or right to spin. Drag up or down to tilt. Scroll to zoom.";
export const HINT_3D = "Drag left or right to spin. Drag up or down to tilt. Scroll to zoom.";

/**
 * Callers pinned at the left edge of the 2D map (mockup v8.3). They don't spin,
 * tilt or zoom with the servers; only their links follow the hub. 2D only.
 */
export const PINNED_AGENTS = [
  { name: "Rigel", sub: "agent · this app", y: 200, other: false },
  { name: "other agent", sub: "connected", y: 340, other: true },
];
const AGENT_X = 30;
const AGENT_W = 150;
const AGENT_H = 56;

/** Where a pinned agent's link meets the hub at this zoom. */
export function agentLinkEnd(index, zoom) {
  return { x: FLAT_CX - FLAT_HUB_R * zoom, y: FLAT_CY + (index === 0 ? -12 : 12) * zoom };
}

export function flatReadout({ tilt, zoom }) {
  return `2D · Tilt ${toDegrees(tilt)}° · Zoom ${zoom.toFixed(1)}×`;
}

export function summarise(rows) {
  const s = { total: rows.length, running: 0, transition: 0, cold: 0, other: 0, tools: 0, errors: [] };
  for (const r of rows) {
    s.tools += Number(r.tools) || 0;
    if (r.state === "running") s.running += 1;
    else if (r.state === "starting" || r.state === "stopping") s.transition += 1;
    else if (r.state === "cold") s.cold += 1;
    else s.other += 1;
    if (r.error) s.errors.push({ name: r.name, error: r.error });
  }
  return s;
}

function FlatMap({ serverRows, hubState }) {
  const [view, setView] = useState({ spin: 0, tilt: FLAT_DEFAULT_TILT, zoom: 1 });
  const mapRef = useRef(null);
  const dragRef = useRef(null);

  // Idle spin, same rate as 3D; pauses while dragging.
  useEffect(() => {
    if (typeof requestAnimationFrame !== "function") return undefined;
    let id = 0;
    const tick = () => {
      if (dragRef.current === null) setView((v) => ({ ...v, spin: v.spin + IDLE_SPIN }));
      id = requestAnimationFrame(tick);
    };
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
  }, []);

  // Drag and wheel. The wheel listener must not be passive so the page doesn't scroll.
  useEffect(() => {
    const el = mapRef.current;
    const onDown = (e) => {
      dragRef.current = { x: e.clientX, y: e.clientY };
      e.preventDefault?.();
    };
    const onMove = (e) => {
      const d = dragRef.current;
      if (d === null) return;
      const dx = e.clientX - d.x;
      const dy = e.clientY - d.y;
      dragRef.current = { x: e.clientX, y: e.clientY };
      // drag up tilts toward flat (straight down); drag down tips it back
      setView((v) => ({ ...v, spin: v.spin + dx * SPIN_PER_PX, tilt: clampFlatTilt(v.tilt - dy * TILT_PER_PX) }));
    };
    const onUp = () => {
      dragRef.current = null;
    };
    const onWheel = (e) => {
      e.preventDefault();
      setView((v) => ({ ...v, zoom: flatWheelZoom(v.zoom, e.deltaY) }));
    };
    el.addEventListener("pointerdown", onDown);
    el.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("wheel", onWheel);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, []);

  const at = ringAngles(serverRows);
  const { zoom, tilt } = view;
  const squash = Math.sin(tilt);
  const nodeR = FLAT_NODE_R * zoom;

  return (
    <>
      <div className="tb-map tb-map--2d" ref={mapRef} data-spin={view.spin.toFixed(4)}>
        <svg
          viewBox={`0 0 ${FLAT_WIDTH} ${FLAT_HEIGHT}`}
          preserveAspectRatio="xMidYMid meet"
          className="tb-svg"
          role="img"
          aria-label={`ToolBox ${hubState}, ${serverRows.length} servers`}
        >
          {/* links from the pinned agents, under everything */}
          {PINNED_AGENTS.map((a, i) => {
            const end = agentLinkEnd(i, zoom);
            return (
              <line
                key={`link-${a.name}`}
                x1={AGENT_X + AGENT_W}
                y1={a.y + AGENT_H / 2}
                x2={end.x}
                y2={end.y}
                className={`tb-link${a.other ? " tb-link--dashed" : ""}`}
                data-agent-link={a.name}
              />
            );
          })}
          <ellipse cx={FLAT_CX} cy={FLAT_CY} rx={FLAT_INNER_R * zoom} ry={FLAT_INNER_R * zoom * squash} className="tb-ring" />
          <ellipse
            cx={FLAT_CX}
            cy={FLAT_CY}
            rx={FLAT_OUTER_R * zoom}
            ry={FLAT_OUTER_R * zoom * squash}
            className="tb-ring tb-ring--outer"
          />
          <g>
            {serverRows.map((s) => {
              const p = at.get(s.name);
              const { x, y } = flatPoint(p.radius, p.angle, view);
              return <line key={s.name} x1={FLAT_CX} y1={FLAT_CY} x2={x} y2={y} className="tb-link" />;
            })}
          </g>
          <circle cx={FLAT_CX} cy={FLAT_CY} r={FLAT_HUB_R * zoom} className="tb-hub" />
          <text x={FLAT_CX} y={FLAT_CY - 4} className="tb-label" textAnchor="middle">ToolBox</text>
          <text x={FLAT_CX} y={FLAT_CY + 14} className="tb-sub" textAnchor="middle">{hubState}</text>
          {serverRows.map((s) => {
            const p = at.get(s.name);
            const { x, y } = flatPoint(p.radius, p.angle, view);
            return (
              <g
                key={s.name}
                className={`tb-node tb-node--${stateTone(s.state)}`}
                data-ring={ringFor(s.state)}
                data-state={s.state}
              >
                <title>{`${s.name} · ${s.state} · ${s.tools} tools`}</title>
                <circle cx={x} cy={y} r={nodeR} className="tb-dot" />
                <text x={x} y={y - nodeR - 7} className="tb-label" textAnchor="middle">{s.name}</text>
                <text x={x} y={y + nodeR + 15} className="tb-sub" textAnchor="middle">
                  {s.state} · {s.tools} tools
                </text>
                {s.error && (
                  <text x={x} y={y + nodeR + 28} className="tb-err" textAnchor="middle">{s.error}</text>
                )}
              </g>
            );
          })}
          {/* pinned agents, drawn last so rings and nodes pass behind them */}
          {PINNED_AGENTS.map((a) => (
            <g key={a.name} className="tb-agent-box" data-agent={a.name}>
              <rect
                x={AGENT_X}
                y={a.y}
                width={AGENT_W}
                height={AGENT_H}
                rx="10"
                className={`tb-agent${a.other ? " tb-agent--other" : ""}`}
              />
              <text x={AGENT_X + AGENT_W / 2} y={a.y + 24} className="tb-label" textAnchor="middle">{a.name}</text>
              <text x={AGENT_X + AGENT_W / 2} y={a.y + 44} className="tb-sub" textAnchor="middle">{a.sub}</text>
            </g>
          ))}
        </svg>
      </div>
      <div className="tb-bar">
        <span className="tb-bar-hint">{HINT_2D}</span>
        <span className="tb-bar-readout">{flatReadout(view)}</span>
      </div>
    </>
  );
}

export default function ToolBoxMap({ serverRows = [], mode = "2d", fallbackReason = null, hubState = "running" }) {
  const [sceneFailed, setSceneFailed] = useState(false);
  const n = serverRows.length;
  const show3D = mode === "3d" && !sceneFailed;
  const reason = fallbackReason ?? (sceneFailed ? "3D unavailable here, showing 2D." : null);
  const sum = summarise(serverRows);

  return (
    <section className={`tb-map-wrap${n > 0 ? "" : " tb-map-wrap--solo"}`} aria-label="Toolbox map">
      <div className="tb-map-col">
        {reason && <p className="tb-fallback" role="status">{reason}</p>}
        {show3D ? (
          <ToolBoxScene
            serverRows={serverRows}
            hubState={hubState}
            hint={HINT_3D}
            onFail={() => setSceneFailed(true)}
          />
        ) : (
          <FlatMap serverRows={serverRows} hubState={hubState} />
        )}
        {n === 0 && <p className="tb-empty">No server detail yet.</p>}
      </div>

      {n > 0 && (
        <aside className="tb-side" aria-label="Server summary">
          <h3>Servers · {sum.total}</h3>
          <div>running &nbsp;&nbsp;{sum.running}</div>
          <div>starting / stopping &nbsp;&nbsp;{sum.transition}</div>
          <div>cold &nbsp;&nbsp;{sum.cold}</div>
          {sum.other > 0 && <div>other &nbsp;&nbsp;{sum.other}</div>}
          <div className="tb-side-gap">Tools available &nbsp;&nbsp;{sum.tools}</div>
          {sum.errors.map((e) => (
            <div key={e.name} className="tb-side-err">{e.name}: {e.error}</div>
          ))}
        </aside>
      )}
    </section>
  );
}
