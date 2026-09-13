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
 *   state   — "idle" | "thinking" | "speaking" (default "idle")
 *   caption — short line under the orb (default "Standing by.")
 */
export default function RigelOrb({ state = "idle", caption = "Standing by." }) {
  return (
    <div className="rigel-orb" data-state={state} role="img" aria-label={`Rigel — ${state}`}>
      <div className="orb-stage">
        <span className="orb-glow" />
        <span className="orb-ring orb-ring--1" />
        <span className="orb-ring orb-ring--2" />
        <span className="orb-ring orb-ring--3" />
        <span className="orb-core" />
        <span className="orb-satellites">
          <i /><i /><i />
        </span>
      </div>
      <div className="orb-caption">{caption}</div>
    </div>
  );
}
