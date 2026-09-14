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

        {/* Orbital 1: 2 electrons on inner ring */}
        <span className="orb-orbital orb-orbital--1">
          <i className="electron electron--1" />
          <i className="electron electron--2" />
        </span>

        {/* Orbital 2: 3 electrons on middle ring */}
        <span className="orb-orbital orb-orbital--2">
          <i className="electron electron--1" />
          <i className="electron electron--2" />
          <i className="electron electron--3" />
        </span>

        {/* Orbital 3: 2 electrons on outer ring */}
        <span className="orb-orbital orb-orbital--3">
          <i className="electron electron--1" />
          <i className="electron electron--2" />
        </span>
      </div>
      <div className="orb-caption">{caption}</div>
    </div>
  );
}
