import { useState } from "react";
import { getConversationTurns } from "../api.js";

/**
 * Chat history (FR-16): every past conversation, read-only. Nothing is deleted.
 * Opening a row loads its transcript here; the main console stays on the current chat.
 */
export default function HistoryPanel({ conversations, activeId, onClose }) {
  const [openId, setOpenId] = useState(null);
  const [loaded, setLoaded] = useState(null); // { id, turns } for the open row
  const [error, setError] = useState(null);

  function openConversation(id) {
    if (openId === id) {
      setOpenId(null);
      return;
    }
    setOpenId(id);
    setError(null);
    getConversationTurns(id)
      .then((data) => setLoaded({ id, turns: data.turns }))
      .catch(() => setError("Couldn't load that chat."));
  }

  return (
    <aside className="history-panel" aria-label="Chat history">
      <div className="history-head">
        <span className="history-title">HISTORY</span>
        <button type="button" className="history-close" onClick={onClose} aria-label="Close history">
          ×
        </button>
      </div>
      <ul className="history-list">
        {conversations.map((c) => {
          const isOpen = c.id === openId;
          const turns = loaded && loaded.id === c.id ? loaded.turns : [];
          const count = `${c.turn_count} ${c.turn_count === 1 ? "message" : "messages"}`;
          return (
            <li key={c.id}>
              <button
                type="button"
                className={`history-row${isOpen ? " is-open" : ""}`}
                onClick={() => openConversation(c.id)}
                aria-expanded={isOpen}
              >
                {c.id === activeId ? "● Current chat" : c.title || "Past chat"} · {count}
              </button>
              {isOpen && (
                <div className="history-turns">
                  {error && <p className="history-error">{error}</p>}
                  {!error && loaded && loaded.id === c.id && turns.length === 0 && (
                    <p className="history-empty">No messages.</p>
                  )}
                  {turns.map((t) => (
                    <p key={t.id} className={`history-turn history-turn--${t.role}`}>
                      <b>{t.role === "user" ? "You" : "Rigel"}:</b> {t.text}
                    </p>
                  ))}
                </div>
              )}
            </li>
          );
        })}
      </ul>
      <p className="history-note">Nothing is deleted.</p>
    </aside>
  );
}
