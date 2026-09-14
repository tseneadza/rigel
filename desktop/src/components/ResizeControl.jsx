import { useState } from "react";

export default function ResizeControl({ orbConfig, onConfigChange }) {
  const [localDiameter, setLocalDiameter] = useState(orbConfig.diameter_px);

  function handleDiameterChange(e) {
    const newDiameter = parseInt(e.target.value, 10);
    setLocalDiameter(newDiameter);
  }

  function handleDiameterRelease() {
    onConfigChange({ ...orbConfig, diameter_px: localDiameter });
  }

  function handleCornerClick(corner) {
    onConfigChange({ ...orbConfig, position_corner: corner, x_pct: null, y_pct: null });
  }

  function handleReset() {
    const defaultConfig = {
      diameter_px: 620,
      position_corner: "center",
      is_minimized: false,
      x_pct: null,
      y_pct: null,
    };
    setLocalDiameter(620);
    onConfigChange(defaultConfig);
  }

  const cornerSymbols = {
    "top-left": "⌜",
    "top-right": "⌝",
    "bottom-left": "⌞",
    "bottom-right": "⌟",
  };

  return (
    <div className="resize-control">
      <div className="resize-row">
        <label>Size:</label>
        <input
          type="range"
          min="60"
          max="620"
          step="10"
          value={localDiameter}
          onChange={handleDiameterChange}
          onMouseUp={handleDiameterRelease}
          onTouchEnd={handleDiameterRelease}
          className="size-slider"
        />
        <span className="size-label">{localDiameter}px</span>
        <button onClick={handleReset} className="reset-btn">
          Reset
        </button>
      </div>

      <div className="resize-row">
        <label>Position:</label>
        <div className="corner-picker">
          {["top-left", "top-right", "bottom-left", "bottom-right"].map(
            (corner) => (
              <button
                key={corner}
                onClick={() => handleCornerClick(corner)}
                className={`corner-btn ${
                  orbConfig.position_corner === corner ? "active" : ""
                }`}
                title={corner}
              >
                {cornerSymbols[corner]}
              </button>
            )
          )}
        </div>
      </div>
    </div>
  );
}
