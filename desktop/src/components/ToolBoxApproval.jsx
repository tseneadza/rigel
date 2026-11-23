/**
 * ToolBoxApproval — the card for a ToolBox server that's asking permission
 * (MCP elicitation, forwarded by ToolBox → Rigel's sidecar, which holds the
 * tool call open until this card is answered).
 *
 * Answered by clicking, or by voice (App.jsx speaks `spoken`, listens once,
 * and listens again a few times if it heard nothing usable
 * without the wake word, and routes the transcript to /interpret). No
 * timeout on Rigel's side (Tony, 2026-11-15); the server itself may give up
 * (osa-system after 120 s), and the card then simply goes away.
 */
import { answerToolboxApproval } from "../api.js";

function details(message) {
  // First line is "osa-system wants to run: fs.delete  [irreversible]";
  // the rest are "  key: value" argument lines, then a "Why…" line.
  const lines = (message || "").split("\n").map((l) => l.trim()).filter(Boolean);
  const head = lines[0] || "";
  const risk = (head.match(/\[([\w-]+)\]/) || [])[1];
  const args = lines.slice(1).filter((l) => !/^why approval|^details:/i.test(l)).slice(0, 4);
  return { head: head.replace(/\s*\[[\w-]+\]\s*/, ""), risk, args };
}

export default function ToolBoxApproval({ approvals, voiceStatus, onAnswered }) {
  if (!approvals || approvals.length === 0) return null;

  async function answer(a, decision) {
    try {
      const updated = await answerToolboxApproval(a.id, decision, "click");
      onAnswered?.(updated);
    } catch (err) {
      onAnswered?.({ ...a, status: "error", detail: err.message });
    }
  }

  return (
    <div className="tb-approvals">
      {approvals.map((a) => {
        const d = details(a.message);
        return (
          <div key={a.id} className="tb-card" role="alertdialog" aria-label={`Approval needed: ${a.tool}`}>
            <div className="tb-card-hd">
              <span>⚠ Approval needed · {a.server}</span>
              {d.risk && <span className="tb-risk">{d.risk}</span>}
            </div>
            <div className="tb-card-q">{d.head}</div>
            {d.args.map((line, i) => (
              <code key={i} className="tb-arg">{line}</code>
            ))}
            <div className="tb-card-said">Rigel said: “{a.spoken}”</div>
            <div className="tb-btns">
              <button type="button" className="tb-yes" onClick={() => answer(a, "approve")}>
                Approve
              </button>
              <button type="button" className="tb-no" onClick={() => answer(a, "decline")}>
                Decline
              </button>
              {voiceStatus === "listening" && (
                <span className="tb-voice">
                  <span className="tb-bars"><i /><i /><i /><i /></span>
                  listening for your answer
                </span>
              )}
              {voiceStatus === "click" && (
                <span className="tb-voice">didn't catch an answer; click to answer</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
