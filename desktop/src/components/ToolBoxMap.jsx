import { useRef, useState } from "react";
import { stateTone } from "../toolboxView.js";

/**
 * ToolBox map (mockup M2 v3). ToolBox is the hub; Rigel and other agents sit
 * at the edge as callers. Running, starting and stopping servers sit on the
 * inner ring; cold and other states sit on the outer ring. Read-only.
 *
 * `serverRows` is [{ name, state, tools, error? }] (state is ToolBox's own
 * label). `mode` is the displayed mode ("2d" | "3d"); `fallbackReason` shows
 * when 3D was asked for but can't render.
 */
const CX = 560;
const CY = 250;
const INNER_R = 110;
const OUTER_R = 205;
const INNER_STATES = new Set(["running", "starting", "stopping"]);

export function ringFor(state) {
  return INNER_STATES.has(state) ? "inner" : "outer";
}

/** Position every row on its ring, spread evenly, starting at the top. */
export function placeOnRings(rows) {
  const inner = rows.filter((r) => ringFor(r.state) === "inner");
  const outer = rows.filter((r) => ringFor(r.state) === "outer");
  const at = new Map();
  const spread = (list, radius, offset) =>
    list.forEach((row, i) => {
      const a = -Math.PI / 2 + offset + (i * 2 * Math.PI) / Math.max(list.length, 1);
      at.set(row.name, { x: CX + radius * Math.cos(a), y: CY + radius * Math.sin(a) });
    });
  spread(inner, INNER_R, 0);
  // Half a step offset on the outer ring so its labels don't sit on the inner ring's spokes.
  spread(outer, OUTER_R, Math.PI / Math.max(outer.length, 1));
  return at;
}

/** Counts and totals for the side panel. */
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

export default function ToolBoxMap({ serverRows = [], mode = "2d", fallbackReason = null, hubState = "running" }) {
  const [turn, setTurn] = useState(0);
  const drag = useRef(null);
  const n = serverRows.length;
  const at = placeOnRings(serverRows);
  const sum = summarise(serverRows);

  const onPointerDown = (e) => {
    drag.current = { x: e.clientX, turn };
  };
  const onPointerMove = (e) => {
    if (!drag.current) return;
    setTurn(drag.current.turn + (e.clientX - drag.current.x) * 0.2);
  };
  const endDrag = () => {
    drag.current = null;
  };

  const is3D = mode === "3d";

  return (
    <section className="tb-map-wrap" aria-label="Toolbox map">
      {fallbackReason && <p className="tb-fallback" role="status">{fallbackReason}</p>}
      <div
        className={`tb-map${is3D ? " tb-map--3d" : ""}`}
        onPointerDown={is3D ? onPointerDown : undefined}
        onPointerMove={is3D ? onPointerMove : undefined}
        onPointerUp={is3D ? endDrag : undefined}
        onPointerLeave={is3D ? endDrag : undefined}
      >
        <svg
          viewBox="0 0 1140 529"
          className="tb-svg"
          role="img"
          aria-label={`ToolBox ${hubState}, ${n} servers`}
          style={is3D ? { transform: `rotateX(58deg) rotateZ(${turn}deg)` } : undefined}
        >
          {/* agents at the edge, linked into the hub */}
          <line x1="210" y1="130" x2={CX - 38} y2={CY - 12} className="tb-link" />
          <line x1="210" y1="300" x2={CX - 38} y2={CY + 12} className="tb-link tb-link--dashed" />
          <rect x="50" y="100" width="150" height="56" rx="10" className="tb-agent" />
          <text x="125" y="124" className="tb-label" textAnchor="middle">Rigel</text>
          <text x="125" y="144" className="tb-sub" textAnchor="middle">agent · this app</text>
          <rect x="50" y="270" width="150" height="56" rx="10" className="tb-agent tb-agent--other" />
          <text x="125" y="294" className="tb-label" textAnchor="middle">other agent</text>
          <text x="125" y="314" className="tb-sub" textAnchor="middle">connected</text>

          {/* rings */}
          <circle cx={CX} cy={CY} r={INNER_R} className="tb-ring" />
          <circle cx={CX} cy={CY} r={OUTER_R} className="tb-ring tb-ring--outer" />

          {/* hub */}
          <circle cx={CX} cy={CY} r="38" className="tb-hub" />
          <text x={CX} y={CY - 4} className="tb-label" textAnchor="middle">ToolBox</text>
          <text x={CX} y={CY + 14} className="tb-sub" textAnchor="middle">{hubState}</text>

          {serverRows.map((s) => {
            const p = at.get(s.name);
            const ring = ringFor(s.state);
            return (
              <g key={s.name} className={`tb-node tb-node--${stateTone(s.state)}`} data-ring={ring} data-state={s.state}>
                <title>{`${s.name} · ${s.state} · ${s.tools} tools`}</title>
                <line x1={CX} y1={CY} x2={p.x} y2={p.y} className="tb-link" />
                <circle cx={p.x} cy={p.y} r="15" className="tb-dot" />
                <text x={p.x} y={p.y - 22} className="tb-label" textAnchor="middle">{s.name}</text>
                <text x={p.x} y={p.y + 32} className="tb-sub" textAnchor="middle">
                  {s.state} · {s.tools} tools
                </text>
                {s.error && (
                  <text x={p.x} y={p.y + 46} className="tb-err" textAnchor="middle">{s.error}</text>
                )}
              </g>
            );
          })}
        </svg>
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
      {n === 0 && <p className="tb-empty">No server detail yet.</p>}
    </section>
  );
}
