import { useEffect, useState } from "react";
import RigelOrb from "./components/RigelOrb.jsx";
import ChatConsole from "./components/ChatConsole.jsx";
import { getLogs, getOrbConfig, saveOrbConfig } from "./api.js";

export default function App() {
  const [turns, setTurns] = useState([]);
  const [orbState, setOrbState] = useState("idle");
  const [online, setOnline] = useState(null); // null = unknown, true/false once probed
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

  const caption =
    online === false
      ? "Offline — start the sidecar."
      : orbState === "thinking"
      ? "Working…"
      : "Standing by.";

  return (
    <div className="app-shell">
      <header className="brandline">
        <span className="brand">RIGEL</span>
        <span className="brand-sub">Responsive Interface for Graphical Execution &amp; Logistics</span>
      </header>

      <main className="stage">
        <RigelOrb
          state={orbState}
          caption={caption}
          diameterPx={orbConfig.diameter_px}
          positionCorner={orbConfig.position_corner}
          isMinimized={orbConfig.is_minimized}
        />
      </main>

      <footer className="dock">
        <ChatConsole
          turns={turns}
          onExchange={handleExchange}
          onBusy={(b) => setOrbState(b ? "thinking" : "idle")}
          orbConfig={orbConfig}
          onOrbConfigChange={handleOrbConfigChange}
        />
      </footer>
    </div>
  );
}
