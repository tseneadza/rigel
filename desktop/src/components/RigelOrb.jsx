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
 *   state           — "idle" | "thinking" | "speaking" (default "idle")
 *   caption         — short line under the orb (default "Standing by.")
 *   diameterPx     — fixed diameter in pixels, or undefined for responsive (default undefined)
 *   positionCorner — "center" | "top-left" | "top-right" | "bottom-left" | "bottom-right" (default "center")
 *   isMinimized    — hide caption if true (default false)
 */
export default function RigelOrb({
  state = "idle",
  caption = "Standing by.",
  diameterPx = undefined,
  positionCorner = "center",
  isMinimized = false,
}) {
  return (
    <div
      className="rigel-orb"
      data-state={state}
      data-position={positionCorner}
      data-minimized={isMinimized}
      style={diameterPx ? { "--orb-diameter": `${diameterPx}px` } : {}}
      role="img"
      aria-label={`Rigel — ${state}`}
    >
      <div className="orb-stage">
        <span className="orb-glow" />
        <span className="orb-ring orb-ring--1" />
        <span className="orb-ring orb-ring--2" />
        <span className="orb-ring orb-ring--3" />
        <span className="orb-core" />

        {/* Orbital ring 1 - 2 electrons */}
        <span className="orb-electrons orb-electrons--1">
          <i className="electron" style={{ animationDelay: "0s" }} />
          <i className="electron" style={{ animationDelay: "4s" }} />
        </span>

        {/* Orbital ring 2 - 3 electrons */}
        <span className="orb-electrons orb-electrons--2">
          <i className="electron" style={{ animationDelay: "0s" }} />
          <i className="electron" style={{ animationDelay: "4s" }} />
          <i className="electron" style={{ animationDelay: "8s" }} />
        </span>

        {/* Orbital ring 3 - 2 electrons */}
        <span className="orb-electrons orb-electrons--3">
          <i className="electron" style={{ animationDelay: "0s" }} />
          <i className="electron" style={{ animationDelay: "8s" }} />
        </span>
      </div>
      <div className="orb-caption">{caption}</div>
    </div>
  );
}
