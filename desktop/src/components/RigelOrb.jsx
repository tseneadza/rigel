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
 * Props:
 *   state           — "idle" | "recording" | "thinking" | "speaking" (default "idle")
 *   caption         — short line under the orb (default "Standing by.")
 *   diameterPx     — fixed diameter in pixels, or undefined for responsive (default undefined)
 *   positionCorner — "center" | "top-left" | "top-right" | "bottom-left" | "bottom-right" | "custom" (default "center")
 *   positionXPct   — left offset as a % of the window, used when positionCorner is "custom"
 *   positionYPct   — top offset as a % of the window, used when positionCorner is "custom"
 *   isMinimized    — hide caption if true (default false)
 *   onDrag         — (xPct, yPct) => void, called when a drag ends
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
}) {
  const [drag, setDrag] = useState(null); // { xPct, yPct } while actively dragging
  const [isDragging, setIsDragging] = useState(false);

  const custom =
    drag ||
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
    setDrag(posFromEvent(e));
  }

  function handlePointerMove(e) {
    if (!isDragging) return;
    setDrag(posFromEvent(e));
  }

  function handlePointerUp(e) {
    if (!isDragging) return;
    setIsDragging(false);
    const final = posFromEvent(e);
    setDrag(final);
    onDrag(final.xPct, final.yPct);
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
