/**
 * Header controls for P2 (mockup v10; mute from v8 M6): mute, New Chat, History.
 * Mute only saves the setting in this step. The desktop listener honours it in
 * the next step (desktop/src-tauri/src/voice/listener.rs).
 */
export default function ConversationControls({
  micOn,
  onToggleMic,
  onNewChat,
  historyOpen,
  onToggleHistory,
}) {
  const muteLabel = micOn ? "Mute Rigel's ears" : "Unmute Rigel's ears";
  return (
    <>
      <button
        type="button"
        className={`icon-btn${micOn ? "" : " icon-btn--muted"}`}
        onClick={onToggleMic}
        aria-label={muteLabel}
        title={muteLabel}
      >
        🎙
      </button>
      <button
        type="button"
        className="icon-btn"
        onClick={onNewChat}
        aria-label="New chat"
        title="New chat"
      >
        ＋
      </button>
      <button
        type="button"
        className={`icon-btn icon-btn--text${historyOpen ? " is-open" : ""}`}
        onClick={onToggleHistory}
        aria-expanded={historyOpen}
        aria-label="Chat history"
        title="Chat history"
      >
        History
      </button>
    </>
  );
}
