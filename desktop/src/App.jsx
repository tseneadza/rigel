import { useEffect, useRef, useState } from "react";
import RigelOrb from "./components/RigelOrb.jsx";
import ChatConsole from "./components/ChatConsole.jsx";
import SettingsPanel from "./components/SettingsPanel.jsx";
import { getLogs, getOrbConfig, saveOrbConfig, getVoiceConfig, sendChat } from "./api.js";
import { restoreRestingBounds, shrinkToCorner } from "./nativeWindow.js";
import { installToggleHotkey } from "./hotkey.js";
import {
  onVoiceState,
  speak,
  setVoiceEnabled,
  onTranscript,
  onVoiceError,
  subscribeInEffect,
  looksLikeSpeech,
} from "./voice.js";

const WORKING_DIAMETER_PX = 90;
const WORKING_WINDOW_PX = WORKING_DIAMETER_PX + 40;
// Rigel must be continuously busy for this long before the window shrinks.
// A voice round trip (transcribe → reply → start speaking) takes well under
// a second, and shrinking/restoring the OS window for that reads as the
// window vanishing and popping back. The shrink is for genuinely long work.
const WORKING_MINIMIZE_DELAY_MS = 2500;

export default function App() {
  const [turns, setTurns] = useState([]);
  const [pendingCommands, setPendingCommands] = useState([]);
  const [orbState, setOrbState] = useState("idle");
  const [online, setOnline] = useState(null); // null = unknown, true/false once probed
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [manualMinimize, setManualMinimize] = useState(false);
  const [orbConfig, setOrbConfig] = useState({
    diameter_px: 620,
    position_corner: "center",
    is_minimized: false,
  });
  const voiceConfigRef = useRef({ tts_voice: null, speak_typed_replies: false });
  // Typed and voice exchanges can be in flight at the same time (the console
  // stays mounted while minimized), so they must not share one busy flag —
  // a typed send finishing would otherwise un-guard the voice flow mid-way.
  const typedBusyRef = useRef(false);
  const voiceBusyRef = useRef(false);
  const isBusy = () => typedBusyRef.current || voiceBusyRef.current;

  // Rehydrate the transcript and orb config on launch.
  useEffect(() => {
    Promise.all([getLogs(50), getOrbConfig()])
      .then(([logsData, configData]) => {
        setTurns(logsData.turns.map((t) => ({ role: t.role, text: t.text })));
        setOrbConfig(configData);
        setOnline(true);
      })
      .catch(() => setOnline(false));
    getVoiceConfig()
      .then((config) => {
        voiceConfigRef.current = config;
        if (config.enabled) {
          setVoiceEnabled(true).catch((err) => {
            console.error("Voice not started (set it up in Settings → Voice):", err.message);
          });
        }
      })
      .catch(() => {});
  }, []);

  // Reflect the native voice pipeline's state (idle/recording/thinking/
  // speaking) onto the orb. Only "idle" is suppressed while a chat request
  // is in flight, so a stray TTS-finished event can't clobber "thinking".
  useEffect(
    () =>
      subscribeInEffect(onVoiceState, (payload) => {
        if (payload.state === "idle" && isBusy()) return;
        setOrbState(payload.state);
      }),
    []
  );

  // A wake-word-triggered command, transcribed natively — feed it through
  // the same chat pipeline typed input uses, then always speak the reply
  // (unlike typed messages, where that's opt-in via Settings).
  useEffect(
    () =>
      subscribeInEffect(onTranscript, async ({ text }) => {
        if (!looksLikeSpeech(text)) {
          console.warn("Dropped non-speech transcript:", text);
          setOrbState("idle");
          return;
        }
        voiceBusyRef.current = true;
        setOrbState("thinking");
        try {
          const res = await sendChat(text);
          handleExchange(text, res, "voice");
        } catch (err) {
          handleExchange(text, { reply: `⚠ Rigel is offline (${err.message}).`, commands: [] }, "voice");
        } finally {
          voiceBusyRef.current = false;
        }
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  useEffect(
    () =>
      subscribeInEffect(onVoiceError, ({ message }) => {
        console.error("Voice pipeline error:", message);
        if (!isBusy()) setOrbState("idle");
      }),
    []
  );

  // Cmd+Shift+R toggles expansion/minimization by hand, on top of the
  // automatic minimize-while-working below.
  useEffect(() => {
    return installToggleHotkey(() => setManualMinimize((m) => !m));
  }, []);

  function handleExchange(userMsg, res, source = "typed") {
    setTurns((prev) => [
      ...prev,
      { role: "user", text: userMsg },
      { role: "rigel", text: res.reply },
    ]);
    setOnline(true);
    const pending = (res.commands || []).filter((c) => c.status === "pending");
    if (pending.length > 0) {
      setPendingCommands((prev) => [...prev, ...pending]);
    }
    const shouldSpeak = source === "voice" || voiceConfigRef.current.speak_typed_replies;
    if (shouldSpeak) {
      speak(res.reply, voiceConfigRef.current.tts_voice).catch(() => setOrbState("idle"));
    }
  }

  // A pending command was approved/denied — drop it from the queue and note
  // the outcome in the transcript, same as any other Rigel turn.
  function handleCommandResolved(updated) {
    setPendingCommands((prev) => prev.filter((c) => c.id !== updated.id));
    const icon = updated.status === "ok" ? "✅" : updated.status === "rejected" ? "🚫" : "⚠";
    setTurns((prev) => [...prev, { role: "rigel", text: `${icon} ${updated.detail}` }]);
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
      : orbState === "recording"
      ? "Listening…"
      : orbState === "thinking"
      ? "Working…"
      : orbState === "speaking"
      ? "Speaking…"
      : "Standing by.";

  // Minimized to just the orb — no header, no console — either because
  // Rigel is working (automatic) or because the hotkey toggled it by hand.
  // Purely a visual override, never persisted, so the user's chosen resting
  // size/position comes right back once it expands again. "recording" is
  // deliberately not included: shrinking the orb into a corner the instant
  // the wake word lands hides the very "I heard you" cue the user is
  // looking at while they speak.
  const isWorking = orbState === "thinking";
  const [autoMinimized, setAutoMinimized] = useState(false);
  useEffect(() => {
    if (!isWorking) {
      setAutoMinimized(false);
      return;
    }
    const timer = setTimeout(() => setAutoMinimized(true), WORKING_MINIMIZE_DELAY_MS);
    return () => clearTimeout(timer);
  }, [isWorking]);
  const minimized = autoMinimized || manualMinimize;
  const displayDiameter = minimized ? WORKING_DIAMETER_PX : orbConfig.diameter_px;
  const displayCorner = minimized ? "center" : orbConfig.position_corner;
  const displayXPct = minimized ? null : orbConfig.x_pct;
  const displayYPct = minimized ? null : orbConfig.y_pct;

  // Shrink the real OS window (not just the CSS orb) down to a small
  // borderless square while minimized, and restore it once expanded again.
  useEffect(() => {
    // Drives `body[data-minimized]` — the CSS drops the opaque starfield so
    // the (transparent-capable) window shows only the orb while shrunk.
    document.body.dataset.minimized = minimized ? "true" : "false";
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
          onBusy={(b) => {
            typedBusyRef.current = b;
            // Don't yank the orb back to idle if a voice exchange or TTS
            // is still under way.
            if (b) setOrbState("thinking");
            else if (!voiceBusyRef.current) setOrbState("idle");
          }}
          hidden={minimized}
          pendingCommands={pendingCommands}
          onCommandResolved={handleCommandResolved}
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
