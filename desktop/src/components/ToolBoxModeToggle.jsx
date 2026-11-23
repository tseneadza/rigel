import { storeMode } from "../toolboxView.js";

/**
 * 2D | 3D switch for the Toolbox view (mockup M2 v2). `mode` is the requested
 * mode (what is remembered), not the displayed one after fallback.
 */
export default function ToolBoxModeToggle({ mode, onChange }) {
  const pick = (next) => {
    storeMode(next);
    onChange(next);
  };
  return (
    <div className="tb-mode" role="group" aria-label="Map mode">
      {["2d", "3d"].map((m) => (
        <button
          key={m}
          type="button"
          className={`tb-mode-btn${mode === m ? " tb-mode-btn--on" : ""}`}
          aria-pressed={mode === m}
          onClick={() => pick(m)}
        >
          {m.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
