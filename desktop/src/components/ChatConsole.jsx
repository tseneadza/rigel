/**
 * ChatConsole — text input + rolling transcript for talking to Rigel.
 *
 * Voice is a later slice; for now this is the single conversation loop. Each
 * send posts to the sidecar, which logs the turn and any command intents.
 */
import { useEffect, useRef, useState } from "react";
import { sendChat } from "../api.js";
import CommandApproval from "./CommandApproval.jsx";
import ToolBoxApproval from "./ToolBoxApproval.jsx";
import ToolSteps from "./ToolSteps.jsx";

export default function ChatConsole({
  turns,
  onExchange,
  onBusy,
  hidden = false,
  pendingCommands = [],
  onCommandResolved,
  toolboxApprovals = [],
  approvalListening = false,
  onApprovalAnswered,
}) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [turns]);

  // While `hidden` (display:none from the parent), the transcript has zero
  // scrollHeight, so a message arriving during that time doesn't actually
  // scroll into view above — catch up once it's shown again.
  useEffect(() => {
    if (hidden) return;
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [hidden]);

  async function submit(e) {
    e.preventDefault();
    const msg = text.trim();
    if (!msg || sending) return;
    setText("");
    setSending(true);
    onBusy?.(true);
    try {
      const res = await sendChat(msg);
      onExchange?.(msg, res);
    } catch (err) {
      onExchange?.(msg, { reply: `⚠ Rigel is offline (${err.message}).`, commands: [] });
    } finally {
      setSending(false);
      onBusy?.(false);
    }
  }

  return (
    <div className="console">
      <div className="transcript" ref={scrollRef}>
        {turns.length === 0 ? (
          <p className="transcript-hint">Speak to Rigel by typing below. Try "open VS Code".</p>
        ) : (
          turns.map((t, i) => (
            <div key={i} className="turn">
              {t.role === "rigel" && <ToolSteps steps={t.tool_steps} />}
              {t.role === "rigel" && t.toolbox_offline && (
                <div className="tool-steps">
                  <span className="tool-chip">
                    <span className="tool-dot tool-dot--error" />
                    ToolBox unreachable · answered without tools
                  </span>
                </div>
              )}
              <div className={`line line--${t.role}`}>
                <span className="line-who">{t.role === "user" ? "You" : "Rigel"}</span>
                <span className="line-text">{t.text}</span>
              </div>
            </div>
          ))
        )}
      </div>
      <ToolBoxApproval
        approvals={toolboxApprovals}
        listening={approvalListening}
        onAnswered={onApprovalAnswered}
      />
      <CommandApproval commands={pendingCommands} onResolved={onCommandResolved} />
      <form className="composer" onSubmit={submit}>
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Message Rigel…"
          autoFocus
        />
        <button type="submit" disabled={sending || !text.trim()}>
          {sending ? "…" : "Send"}
        </button>
      </form>
    </div>
  );
}
