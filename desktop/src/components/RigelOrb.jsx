import { useState } from "react";

const clamp = (v, min, max) => Math.min(max, Math.max(min, v));

/**
 * RigelOrb — Rigel's presence orb.
 *
 * A luminous, breathing ice-blue sphere in the visual language of the OSA orb
 * (white-hot core, layered glow, expanding ripple rings, orbiting satellites),
 * retuned to Rigel's "blazing blue" identity. Fully scalable: the orb sizes off
 * `min(64vmin, 620px)` so it fills the screen on first launch and scales with
 * the viewport.
 *
 * State drives the hue via one CSS custom property (`--orb`, an "r,g,b" triple)
 * on the root, so retuning a state color is a one-line change.
 *
 * Dragging works differently depending on `isMinimized`: at rest, dragging
 * repositions the orb within its own (large) window via a CSS "custom"
 * position, reported through `onDrag` on release. Minimized, the window
 * itself is a small square parked at a screen corner/position — there,
 * dragging moves that real OS window live and is reported through
 * `onMinimizedDrag` instead, since a CSS offset inside a window that small
 * wouldn't visibly relocate anything.
 *
 * Props:
 *   state           — "idle" | "recording" | "thinking" | "speaking" (default "idle")
 *   caption         — short line under the orb (default "Standing by.")
 *   diameterPx      — fixed diameter in pixels, or undefined for responsive (default undefined)
 *   positionCorner  — "center" | "top-left" | "top-right" | "bottom-left" | "bottom-right" | "custom" (default "center")
 *   positionXPct    — left offset as a % of the window, used when positionCorner is "custom"
 *   positionYPct    — top offset as a % of the window, used when positionCorner is "custom"
 *   isMinimized     — hide caption if true; also switches dragging to move the
 *                     real OS window instead of the CSS position (default false)
 *   onDrag          — (xPct, yPct) => void, called when a resting-orb drag ends
 *   onMinimizedDrag — (phase, screenX, screenY) => void, phase is "start" | "move" | "end",
 *                     screenX/screenY are the pointer's absolute screen coordinates (CSS px);
 *                     only fires while isMinimized
 */
export default function RigelOrb({
  state = "idle",
  caption = "Standing by.",
  diameterPx = undefined,
  positionCorner = "center",
  positionXPct = null,
  positionYPct = null,
  isMinimized = false,
  onDrag = () => {},
  onMinimizedDrag = () => {},
}) {
  const [drag, setDrag] = useState(null); // { xPct, yPct } while actively dragging (resting orb only)
  const [isDragging, setIsDragging] = useState(false);

  // `drag` (a resting-orb-only CSS preview) survives a minimize/restore
  // cycle since this component never unmounts — ignore it while minimized
  // so a stale resting-drag position can't bleed into the tiny window.
  const custom =
    (!isMinimized && drag) ||
    (positionCorner === "custom" && positionXPct != null && positionYPct != null
      ? { xPct: positionXPct, yPct: positionYPct }
      : null);

  function posFromEvent(e) {
    return {
      xPct: clamp((e.clientX / window.innerWidth) * 100, 4, 96),
      yPct: clamp((e.clientY / window.innerHeight) * 100, 4, 96),
    };
  }

  function handlePointerDown(e) {
    if (e.button !== 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    setIsDragging(true);
    if (isMinimized) {
      onMinimizedDrag("start", e.screenX, e.screenY);
    } else {
      setDrag(posFromEvent(e));
    }
  }

  function handlePointerMove(e) {
    if (!isDragging) return;
    if (isMinimized) {
      onMinimizedDrag("move", e.screenX, e.screenY);
    } else {
      setDrag(posFromEvent(e));
    }
  }

  function handlePointerUp(e) {
    if (!isDragging) return;
    setIsDragging(false);
    if (isMinimized) {
      onMinimizedDrag("end", e.screenX, e.screenY);
    } else {
      const final = posFromEvent(e);
      setDrag(final);
      onDrag(final.xPct, final.yPct);
    }
  }

  return (
    <div
      className="rigel-orb"
      data-state={state}
      data-position={custom ? "custom" : positionCorner}
      data-minimized={isMinimized}
      data-dragging={isDragging || undefined}
      style={{
        ...(diameterPx ? { "--orb-diameter": `${diameterPx}px` } : {}),
        ...(custom ? { "--orb-x": `${custom.xPct}%`, "--orb-y": `${custom.yPct}%` } : {}),
      }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      role="img"
      aria-label={`Rigel — ${state}`}
    >
      <div className="orb-stage">
        <span className="orb-glow" />
        <span className="orb-ring orb-ring--1" />
        <span className="orb-ring orb-ring--2" />
        <span className="orb-ring orb-ring--3" />
        <span className="orb-core" />

        {/* Three tilted 3D orbits; --a spreads electrons around each ring */}
        <span className="orb-electrons orb-electrons--1">
          <i className="electron" style={{ "--a": "0deg" }} />
          <i className="electron" style={{ "--a": "180deg" }} />
        </span>
        <span className="orb-electrons orb-electrons--2">
          <i className="electron" style={{ "--a": "0deg" }} />
          <i className="electron" style={{ "--a": "120deg" }} />
          <i className="electron" style={{ "--a": "240deg" }} />
        </span>
        <span className="orb-electrons orb-electrons--3">
          <i className="electron" style={{ "--a": "90deg" }} />
          <i className="electron" style={{ "--a": "270deg" }} />
        </span>
      </div>
      <div className="orb-caption">{caption}</div>
    </div>
  );
}
