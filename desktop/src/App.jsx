import { useEffect, useState } from "react";
import RigelOrb from "./components/RigelOrb.jsx";
import ChatConsole from "./components/ChatConsole.jsx";
import { getLogs } from "./api.js";

export default function App() {
  const [turns, setTurns] = useState([]);
  const [orbState, setOrbState] = useState("idle");
  const [online, setOnline] = useState(null); // null = unknown, true/false once probed

  // Rehydrate the transcript from Rigel's own log store on launch.
  useEffect(() => {
    getLogs(50)
      .then((d) => {
        setTurns(d.turns.map((t) => ({ role: t.role, text: t.text })));
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
        <RigelOrb state={orbState} caption={caption} />
      </main>

      <footer className="dock">
        <ChatConsole
          turns={turns}
          onExchange={handleExchange}
          onBusy={(b) => setOrbState(b ? "thinking" : "idle")}
        />
      </footer>
    </div>
  );
}
