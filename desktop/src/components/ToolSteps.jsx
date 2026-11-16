/**
 * ToolSteps — the ToolBox steps behind one Rigel reply, folded into a single
 * "used N tools" line (Tony, 2026-11-15: fold them) that expands into chips.
 *
 * Step shape (from the sidecar's /chat `tool_steps`, and /logs on relaunch):
 *   {kind: "need"|"call", tool, arguments, status: ok|error|declined|expired,
 *    ms, detail, approval: {status, answered_via} | null}
 */
import { useState } from "react";

function fmtMs(ms) {
  if (ms == null) return "";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`;
}

function callNote(step) {
  const via = step.approval?.answered_via;
  if (step.status === "declined") return `declined${via ? ` by ${via}` : ""}`;
  if (step.status === "expired") return "server stopped waiting";
  if (step.status === "error") return step.detail || "failed";
  return via ? `approved by ${via}` : "";
}

export default function ToolSteps({ steps }) {
  const [open, setOpen] = useState(false);
  if (!steps || steps.length === 0) return null;
  const calls = steps.filter((s) => s.kind === "call");
  const problems = calls.filter((s) => s.status !== "ok").length;
  const label =
    calls.length === 0
      ? `looked for tools (${steps.length})`
      : `used ${calls.length} tool${calls.length === 1 ? "" : "s"}`;

  return (
    <div className="tool-steps">
      <button
        type="button"
        className={`tool-fold ${problems ? "tool-fold--warn" : ""}`}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="tool-fold-caret">{open ? "▾" : "▸"}</span>
        ToolBox · {label}
        {problems > 0 && <span className="tool-fold-note"> · {problems} not done</span>}
      </button>
      {open && (
        <div className="tool-chips">
          {steps.map((s, i) =>
            s.kind === "need" ? (
              <span key={i} className="tool-chip tool-chip--find">
                ⌕ need("{s.tool}") → {s.detail || "no matches"}
              </span>
            ) : (
              <span key={i} className="tool-chip">
                <span className={`tool-dot tool-dot--${s.status}`} />
                {s.tool}
                <span className="tool-ms">
                  {" "}· {fmtMs(s.ms)}
                  {callNote(s) ? ` · ${callNote(s)}` : ""}
                </span>
              </span>
            )
          )}
        </div>
      )}
    </div>
  );
}
