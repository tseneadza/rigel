import { useEffect, useState } from "react";
import RigelOrb from "./components/RigelOrb.jsx";
import ChatConsole from "./components/ChatConsole.jsx";
import SettingsPanel from "./components/SettingsPanel.jsx";
import { getLogs, getOrbConfig, saveOrbConfig } from "./api.js";

const WORKING_DIAMETER_PX = 90;
const WORKING_CORNER = "bottom-right";

export default function App() {
  const [turns, setTurns] = useState([]);
  const [orbState, setOrbState] = useState("idle");
  const [online, setOnline] = useState(null); // null = unknown, true/false once probed
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [orbConfig, setOrbConfig] = useState({
    diameter_px: 620,
    position_corner: "center",
    is_minimized: false,
  });

  // Rehydrate the transcript and orb config on launch.
  useEffect(() => {
    Promise.all([getLogs(50), getOrbConfig()])
      .then(([logsData, configData]) => {
        setTurns(logsData.turns.map((t) => ({ role: t.role, text: t.text })));
        setOrbConfig(configData);
        setOnline(true);
      })
      .catch(() => setOnline(false));
  }, []);

  function handleExchange(userMsg, res) {
    setTurns((prev) => [
      ...prev,
      { role: "user", text: userMsg },
      { role: "rigel", text: res.reply },
    ]);
    setOnline(true);
  }

  function handleOrbConfigChange(newConfig) {
    setOrbConfig(newConfig);
    saveOrbConfig(newConfig).catch((err) => {
      console.error("Failed to save orb config:", err);
    });
  }

  function handleOrbDrag(xPct, yPct) {
    handleOrbConfigChange({
      ...orbConfig,
      position_corner: "custom",
      x_pct: xPct,
      y_pct: yPct,
    });
  }

  const caption =
    online === false
      ? "Offline — start the sidecar."
      : orbState === "thinking"
      ? "Working…"
      : "Standing by.";

  // While Rigel is working, tuck the orb into a corner as a compact prompt —
  // a purely visual override, never persisted, so the user's chosen resting
  // size/position comes right back once orbState returns to "idle".
  const isWorking = orbState === "thinking";
  const displayDiameter = isWorking ? WORKING_DIAMETER_PX : orbConfig.diameter_px;
  const displayCorner = isWorking ? WORKING_CORNER : orbConfig.position_corner;
  const displayXPct = isWorking ? null : orbConfig.x_pct;
  const displayYPct = isWorking ? null : orbConfig.y_pct;

  return (
    <div className="app-shell">
      <header className="brandline" data-tauri-drag-region>
        <span className="brand">RIGEL</span>
        <span className="brand-sub">Really Intelligent Graphical Execution Layer</span>
        <button
          className="settings-btn"
          onClick={() => setSettingsOpen(true)}
          aria-label="Open settings"
          title="Settings"
        >
          ⚙
        </button>
      </header>

      <main className="stage">
        <RigelOrb
          state={orbState}
          caption={caption}
          diameterPx={displayDiameter}
          positionCorner={displayCorner}
          positionXPct={displayXPct}
          positionYPct={displayYPct}
          isMinimized={isWorking || orbConfig.is_minimized}
          onDrag={handleOrbDrag}
        />
      </main>

      <footer className="dock">
        <ChatConsole
          turns={turns}
          onExchange={handleExchange}
          onBusy={(b) => setOrbState(b ? "thinking" : "idle")}
        />
      </footer>

      <SettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        orbConfig={orbConfig}
        onOrbConfigChange={handleOrbConfigChange}
      />
    </div>
  );
}
