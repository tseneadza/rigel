import { useEffect, useState } from "react";
import RigelOrb from "./components/RigelOrb.jsx";
import ChatConsole from "./components/ChatConsole.jsx";
import SettingsPanel from "./components/SettingsPanel.jsx";
import { getLogs, getOrbConfig, saveOrbConfig } from "./api.js";
import { restoreRestingBounds, shrinkToCorner } from "./nativeWindow.js";
import { installToggleHotkey } from "./hotkey.js";

const WORKING_DIAMETER_PX = 90;
const WORKING_WINDOW_PX = WORKING_DIAMETER_PX + 40;

export default function App() {
  const [turns, setTurns] = useState([]);
  const [orbState, setOrbState] = useState("idle");
  const [online, setOnline] = useState(null); // null = unknown, true/false once probed
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [manualMinimize, setManualMinimize] = useState(false);
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

  // Cmd+Shift+R toggles expansion/minimization by hand, on top of the
  // automatic minimize-while-working below.
  useEffect(() => {
    return installToggleHotkey(() => setManualMinimize((m) => !m));
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

  // Minimized to just the orb — no header, no console — either because
  // Rigel is working (automatic) or because the hotkey toggled it by hand.
  // Purely a visual override, never persisted, so the user's chosen resting
  // size/position comes right back once it expands again.
  const isWorking = orbState === "thinking";
  const minimized = isWorking || manualMinimize;
  const displayDiameter = minimized ? WORKING_DIAMETER_PX : orbConfig.diameter_px;
  const displayCorner = minimized ? "center" : orbConfig.position_corner;
  const displayXPct = minimized ? null : orbConfig.x_pct;
  const displayYPct = minimized ? null : orbConfig.y_pct;

  // Shrink the real OS window (not just the CSS orb) down to a small
  // borderless square while minimized, and restore it once expanded again.
  useEffect(() => {
    if (minimized) {
      shrinkToCorner({ widthPx: WORKING_WINDOW_PX, heightPx: WORKING_WINDOW_PX });
    } else {
      restoreRestingBounds();
    }
  }, [minimized]);

  return (
    <div className="app-shell">
      {!minimized && (
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
      )}

      <main className="stage">
        <RigelOrb
          state={orbState}
          caption={caption}
          diameterPx={displayDiameter}
          positionCorner={displayCorner}
          positionXPct={displayXPct}
          positionYPct={displayYPct}
          isMinimized={minimized || orbConfig.is_minimized}
          onDrag={handleOrbDrag}
        />
      </main>

      {/* Kept mounted (just hidden) while minimized so an in-flight send isn't torn down mid-request. */}
      <footer className="dock" style={minimized ? { display: "none" } : undefined}>
        <ChatConsole
          turns={turns}
          onExchange={handleExchange}
          onBusy={(b) => setOrbState(b ? "thinking" : "idle")}
          hidden={minimized}
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
