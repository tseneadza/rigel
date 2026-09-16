/**
 * ChatConsole — text input + rolling transcript for talking to Rigel.
 *
 * Voice is a later slice; for now this is the single conversation loop. Each
 * send posts to the sidecar, which logs the turn and any command intents.
 */
import { useEffect, useRef, useState } from "react";
import { sendChat } from "../api.js";

export default function ChatConsole({ turns, onExchange, onBusy }) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [turns]);

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
            <div key={i} className={`line line--${t.role}`}>
              <span className="line-who">{t.role === "user" ? "You" : "Rigel"}</span>
              <span className="line-text">{t.text}</span>
            </div>
          ))
        )}
      </div>
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
