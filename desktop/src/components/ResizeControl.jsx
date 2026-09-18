import { useState } from "react";

const DEFAULT_MIN_DIAMETER_PX = 90;
const DEFAULT_MAX_DIAMETER_PX = 620;

export default function ResizeControl({ orbConfig, onConfigChange }) {
  const [localMinDiameter, setLocalMinDiameter] = useState(
    orbConfig.min_diameter_px ?? DEFAULT_MIN_DIAMETER_PX
  );
  const [localMaxDiameter, setLocalMaxDiameter] = useState(
    orbConfig.diameter_px ?? DEFAULT_MAX_DIAMETER_PX
  );

  function handleMinDiameterChange(e) {
    setLocalMinDiameter(parseInt(e.target.value, 10));
  }

  function handleMinDiameterRelease() {
    onConfigChange({ ...orbConfig, min_diameter_px: localMinDiameter });
  }

  function handleMaxDiameterChange(e) {
    setLocalMaxDiameter(parseInt(e.target.value, 10));
  }

  function handleMaxDiameterRelease() {
    onConfigChange({ ...orbConfig, diameter_px: localMaxDiameter });
  }

  function handleCornerClick(corner) {
    onConfigChange({ ...orbConfig, position_corner: corner, x_pct: null, y_pct: null });
  }

  function handleReset() {
    const defaultConfig = {
      diameter_px: DEFAULT_MAX_DIAMETER_PX,
      min_diameter_px: DEFAULT_MIN_DIAMETER_PX,
      position_corner: "center",
      is_minimized: false,
      x_pct: null,
      y_pct: null,
    };
    setLocalMinDiameter(DEFAULT_MIN_DIAMETER_PX);
    setLocalMaxDiameter(DEFAULT_MAX_DIAMETER_PX);
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
        <label>Minimized size:</label>
        <input
          type="range"
          min="40"
          max="200"
          step="10"
          value={localMinDiameter}
          onChange={handleMinDiameterChange}
          onMouseUp={handleMinDiameterRelease}
          onTouchEnd={handleMinDiameterRelease}
          className="size-slider"
        />
        <span className="size-label">{localMinDiameter}px</span>
      </div>

      <div className="resize-row">
        <label>Expanded size:</label>
        <input
          type="range"
          min="200"
          max="620"
          step="10"
          value={localMaxDiameter}
          onChange={handleMaxDiameterChange}
          onMouseUp={handleMaxDiameterRelease}
          onTouchEnd={handleMaxDiameterRelease}
          className="size-slider"
        />
        <span className="size-label">{localMaxDiameter}px</span>
        <button onClick={handleReset} className="reset-btn">
          Reset
        </button>
      </div>

      <div className="resize-row">
        <label>Minimized position:</label>
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
