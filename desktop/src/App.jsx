import { useEffect, useRef, useState } from "react";
import RigelOrb from "./components/RigelOrb.jsx";
import ChatConsole from "./components/ChatConsole.jsx";
import SettingsPanel from "./components/SettingsPanel.jsx";
import BrainChip from "./components/BrainChip.jsx";
import ViewArea from "./components/ViewArea.jsx";
import RunningApps from "./components/RunningApps.jsx";
import ConversationControls from "./components/ConversationControls.jsx";
import HistoryPanel from "./components/HistoryPanel.jsx";
import { setWakeWordMuted } from "./voice.js";
import {
  getLogs,
  getOrbConfig,
  saveOrbConfig,
  getVoiceConfig,
  sendChat,
  getToolboxApprovals,
  getToolboxStatus,
  interpretToolboxApproval,
  getMicWakeWord,
  saveMicWakeWord,
  listConversations,
  startNewConversation,
} from "./api.js";
import {
  restoreRestingBounds,
  shrinkToCorner,
  beginWindowDrag,
  dragWindowTo,
  endWindowDrag,
} from "./nativeWindow.js";
import { installToggleHotkey } from "./hotkey.js";
import {
  onVoiceState,
  speak,
  setVoiceEnabled,
  onTranscript,
  onVoiceError,
  subscribeInEffect,
  looksLikeSpeech,
  listenOnce,
} from "./voice.js";

// How often to check for ToolBox approvals while a reply is in flight, and
// how often to refresh the ToolBox badge otherwise.
const APPROVAL_POLL_MS = 600;
const TOOLBOX_STATUS_POLL_MS = 20000;

// Fallback only — used before orbConfig has loaded from the sidecar; the
// real minimized size comes from orbConfig.min_diameter_px (Settings → Orb).
const DEFAULT_MIN_DIAMETER_PX = 90;
const MINIMIZED_WINDOW_MARGIN_PX = 40;
// Rigel must be continuously busy for this long before the window shrinks.
// A voice round trip (transcribe → reply → start speaking) takes well under
// a second, and shrinking/restoring the OS window for that reads as the
// window vanishing and popping back. The shrink is for genuinely long work.
const WORKING_MINIMIZE_DELAY_MS = 2500;
// Main-view choices (PRD v6 FR-1). Non-chat views dock the orb at this size.
const VIEWS = [
  { id: "chat", label: "Agent Chat" },
  { id: "toolbox", label: "Toolbox" },
  { id: "presentation", label: "Presentation" },
];
const DOCKED_DIAMETER_PX = 120;

export default function App() {
  const [turns, setTurns] = useState([]);
  const [pendingCommands, setPendingCommands] = useState([]);
  const [orbState, setOrbState] = useState("idle");
  const [online, setOnline] = useState(null); // null = unknown, true/false once probed
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [manualMinimize, setManualMinimize] = useState(false);
  const [activeView, setActiveView] = useState("chat");
  const [orbConfig, setOrbConfig] = useState({
    diameter_px: 620,
    min_diameter_px: DEFAULT_MIN_DIAMETER_PX,
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

  // ToolBox: approvals a server is waiting on (only possible while a /chat
  // is in flight), whether Rigel is listening for a spoken answer, and the
  // header badge.
  const [chatsInFlight, setChatsInFlight] = useState(0);
  const [toolboxApprovals, setToolboxApprovals] = useState([]);
  const approvalsRef = useRef([]);
  const announcedApprovalsRef = useRef(new Set());
  const [approvalListening, setApprovalListening] = useState(false);
  const [toolboxStatus, setToolboxStatus] = useState(null);

  // P2: mute (wake-word listening on/off), New Chat, and history.
  const [micOn, setMicOn] = useState(true);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [activeConvId, setActiveConvId] = useState(null);

  function refreshConversations() {
    listConversations()
      .then((data) => {
        setConversations(data.conversations);
        setActiveConvId(data.active_id);
      })
      .catch(() => {});
  }

  useEffect(() => {
    getMicWakeWord()
      .then((cfg) => {
        setMicOn(cfg.enabled);
        setWakeWordMuted(!cfg.enabled).catch(() => {});
      })
      .catch(() => {});
    refreshConversations();
  }, []);

  function handleToggleMic() {
    const next = !micOn;
    setMicOn(next);
    setWakeWordMuted(!next).catch(() => {});
    saveMicWakeWord(next).catch(() => {
      setMicOn(!next);
      setWakeWordMuted(next).catch(() => {});
    });
  }

  // New Chat clears only the transcript. Pending approvals stay in state (NFR-4).
  function handleNewChat() {
    startNewConversation()
      .then(() => {
        setTurns([]);
        refreshConversations();
      })
      .catch(() => {});
  }

  function handleToggleHistory() {
    if (!historyOpen) refreshConversations();
    setHistoryOpen((open) => !open);
  }

  // Rehydrate the transcript and orb config on launch.
  useEffect(() => {
    Promise.all([getLogs(50), getOrbConfig()])
      .then(([logsData, configData]) => {
        setTurns(logsData.turns.map((t) => ({ role: t.role, text: t.text, tool_steps: t.tool_steps })));
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
        // A ToolBox server is waiting on an answer: this utterance is the
        // answer, not a new request (with or without the wake word).
        if (approvalsRef.current.length > 0) {
          await answerApprovalByVoice(approvalsRef.current[0], text);
          return;
        }
        voiceBusyRef.current = true;
        setOrbState("thinking");
        setChatsInFlight((n) => n + 1);
        try {
          const res = await sendChat(text);
          handleExchange(text, res, "voice");
        } catch (err) {
          handleExchange(text, { reply: `⚠ Rigel is offline (${err.message}).`, commands: [] }, "voice");
        } finally {
          voiceBusyRef.current = false;
          setChatsInFlight((n) => n - 1);
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

  // ── ToolBox approvals ───────────────────────────────────────────────
  // Poll while a reply is in flight; that's the only time a ToolBox server
  // can be waiting on an answer (the sidecar holds the /chat open).
  useEffect(() => {
    if (chatsInFlight <= 0) {
      approvalsRef.current = [];
      setToolboxApprovals([]);
      setApprovalListening(false);
      return;
    }
    let stopped = false;
    const tick = () =>
      getToolboxApprovals()
        .then(({ approvals }) => {
          if (stopped) return;
          approvalsRef.current = approvals;
          setToolboxApprovals(approvals);
          if (approvals.length === 0) setApprovalListening(false);
          for (const a of approvals) {
            if (announcedApprovalsRef.current.has(a.id)) continue;
            announcedApprovalsRef.current.add(a.id);
            announceApproval(a);
          }
        })
        .catch(() => {});
    tick();
    const timer = setInterval(tick, APPROVAL_POLL_MS);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatsInFlight > 0]);

  // Say what needs approving, then listen once without the wake word.
  // Only when voice is on; otherwise the card alone asks.
  async function askOutLoud(sentence) {
    if (!voiceConfigRef.current.enabled) return;
    try {
      await speak(sentence, voiceConfigRef.current.tts_voice);
      await listenOnce();
      setApprovalListening(true);
    } catch (err) {
      console.error("Couldn't ask for approval out loud:", err);
      setApprovalListening(false);
    }
  }

  function announceApproval(a) {
    askOutLoud(a.spoken);
  }

  async function answerApprovalByVoice(approval, text) {
    setApprovalListening(false);
    setOrbState("thinking");
    try {
      const r = await interpretToolboxApproval(approval.id, text, "voice");
      if (r.decision === "unclear" && r.follow_up) {
        await askOutLoud(r.follow_up);
      } else if (r.decision === "approve" || r.decision === "decline") {
        const left = approvalsRef.current.filter((a) => a.id !== approval.id);
        approvalsRef.current = left;
        setToolboxApprovals(left);
      }
    } catch (err) {
      console.error("Couldn't send the spoken answer:", err);
    }
  }

  function handleApprovalAnswered(updated) {
    const left = approvalsRef.current.filter((a) => a.id !== updated.id);
    approvalsRef.current = left;
    setToolboxApprovals(left);
    setApprovalListening(false);
  }

  // Header badge: is ToolBox reachable?
  useEffect(() => {
    let stopped = false;
    const tick = () =>
      getToolboxStatus()
        .then((st) => !stopped && setToolboxStatus(st))
        .catch(() => !stopped && setToolboxStatus(null));
    tick();
    const timer = setInterval(tick, TOOLBOX_STATUS_POLL_MS);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, []);

  function handleExchange(userMsg, res, source = "typed") {
    setTurns((prev) => [
      ...prev,
      { role: "user", text: userMsg },
      {
        role: "rigel",
        text: res.reply,
        tool_steps: res.tool_steps,
        toolbox_offline: res.toolbox?.state === "offline",
      },
    ]);
    setOnline(true);
    if (res.toolbox?.state === "offline") {
      setToolboxStatus((st) => ({ ...(st || {}), state: "offline" }));
    }
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

  // Dragging only happens while minimized (see RigelOrb) — it moves the real
  // OS window live, the same way dragging a titlebar would, rather than a
  // CSS position inside a window that never moves. On release, the final
  // spot is persisted the normal way so it's restored on the next minimize.
  function handleMinimizedDrag(phase, screenX, screenY) {
    if (phase === "start") {
      beginWindowDrag(screenX, screenY);
    } else if (phase === "move") {
      dragWindowTo(screenX, screenY);
    } else if (phase === "end") {
      dragWindowTo(screenX, screenY);
      endWindowDrag().then((pos) => {
        if (pos) handleOrbDrag(pos.xPct, pos.yPct);
      });
    }
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
  // A ToolBox approval needs the console (its card and buttons), so Rigel
  // expands while one is waiting, even mid-reply or after ⌘⇧R.
  const awaitingApproval = toolboxApprovals.length > 0;
  const minimized = (autoMinimized || manualMinimize) && !awaitingApproval;
  // Settings → Orb's size slider now covers the expanded/resting ("maximum")
  // size; its minimized ("minimum") size is separate, defaulting to the
  // constant this used to be hardcoded to. The position picker (and dragging)
  // governs only where the orb parks while minimized, so it's forced to
  // "center" at rest — that's a CSS position within the (large) resting
  // window, unrelated to the minimized window's real screen placement below.
  const minDiameterPx = orbConfig.min_diameter_px ?? DEFAULT_MIN_DIAMETER_PX;
  const minimizedWindowPx = minDiameterPx + MINIMIZED_WINDOW_MARGIN_PX;
  const displayDiameter = minimized ? minDiameterPx : orbConfig.diameter_px;
  const displayCorner = minimized ? "center" : orbConfig.position_corner;
  const displayXPct = minimized ? null : orbConfig.x_pct;
  const displayYPct = minimized ? null : orbConfig.y_pct;
  // Non-chat views dock the orb in the bottom-right corner inside the normal-size
  // window; no OS-window shrink (PRD v6 FR-9). Minimizing still shrinks the window.
  const docked = activeView !== "chat" && !minimized;
  const orbDiameter = docked ? DOCKED_DIAMETER_PX : displayDiameter;
  const orbCorner = docked ? "docked" : displayCorner;
  const orbX = docked ? null : displayXPct;
  const orbY = docked ? null : displayYPct;

  // Shrink the real OS window (not just the CSS orb) down to a small
  // borderless square while minimized, and restore it once expanded again.
  // The square itself is placed at orbConfig's chosen corner/custom position
  // so the minimized orb actually lands where Settings → Orb says it should.
  useEffect(() => {
    // Drives `body[data-minimized]` — the CSS drops the opaque starfield so
    // the (transparent-capable) window shows only the orb while shrunk.
    document.body.dataset.minimized = minimized ? "true" : "false";
    if (minimized) {
      shrinkToCorner({
        widthPx: minimizedWindowPx,
        heightPx: minimizedWindowPx,
        corner: orbConfig.position_corner,
        xPct: orbConfig.x_pct,
        yPct: orbConfig.y_pct,
      });
    } else {
      restoreRestingBounds();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [minimized]);

  return (
    <div className="app-shell">
      {!minimized && (
        <header className="brandline" data-tauri-drag-region>
          <span className="brand">RIGEL</span>
          <span className="brand-sub">Really Intelligent Graphical Execution Layer</span>
          <select className="view-select" aria-label="Main view" value={activeView} onChange={(e) => setActiveView(e.target.value)}>
            {VIEWS.map((v) => (
              <option key={v.id} value={v.id}>{v.label}</option>
            ))}
          </select>
          <RunningApps />
          {toolboxStatus && toolboxStatus.state !== "disabled" && (
            <span
              className={`tb-badge ${toolboxStatus.state === "connected" ? "" : "tb-badge--off"}`}
              title={toolboxStatus.url || ""}
            >
              <span className="tb-badge-dot" />
              {toolboxStatus.state === "connected"
                ? `ToolBox · ${toolboxStatus.servers} servers`
                : "ToolBox offline"}
            </span>
          )}
          <ConversationControls
            micOn={micOn}
            onToggleMic={handleToggleMic}
            onNewChat={handleNewChat}
            historyOpen={historyOpen}
            onToggleHistory={handleToggleHistory}
          />
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
          diameterPx={orbDiameter}
          positionCorner={orbCorner}
          positionXPct={orbX}
          positionYPct={orbY}
          isMinimized={minimized || orbConfig.is_minimized}
          onDrag={handleOrbDrag}
          onMinimizedDrag={handleMinimizedDrag}
        />
        {activeView !== "chat" && <ViewArea view={activeView} />}
        {!minimized && <BrainChip />}
        {!minimized && historyOpen && (
          <HistoryPanel
            conversations={conversations}
            activeId={activeConvId}
            onClose={() => setHistoryOpen(false)}
          />
        )}
      </main>

      {/* Kept mounted (just hidden) while minimized so an in-flight send isn't torn down mid-request. */}
      <footer className="dock" style={minimized ? { display: "none" } : undefined}>
        <ChatConsole
          turns={turns}
          onExchange={handleExchange}
          onBusy={(b) => {
            typedBusyRef.current = b;
            setChatsInFlight((n) => n + (b ? 1 : -1));
            // Don't yank the orb back to idle if a voice exchange or TTS
            // is still under way.
            if (b) setOrbState("thinking");
            else if (!voiceBusyRef.current) setOrbState("idle");
          }}
          hidden={minimized}
          pendingCommands={pendingCommands}
          onCommandResolved={handleCommandResolved}
          toolboxApprovals={toolboxApprovals}
          approvalListening={approvalListening}
          onApprovalAnswered={handleApprovalAnswered}
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
