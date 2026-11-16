/**
 * CommandApproval — one card per command Rigel is waiting to run.
 *
 * Detected commands come back from /chat already validated (`executor.py`
 * resolved their args), so what's shown here — an app name, or an absolute
 * file path — is exactly what will execute on Approve.
 */
import { approveCommand, rejectCommand } from "../api.js";

function describe(cmd) {
  if (cmd.action === "app_action") {
    const { app_id, tool, tool_args } = cmd.args;
    const label = String(tool ?? "").replace(/_/g, " ");
    const detail = Object.values(tool_args ?? {}).filter(Boolean).join(", ");
    return `${app_id}: ${label}${detail ? ` (${detail})` : ""}`.trim();
  }
  if (cmd.action === "click_menu_item") {
    const { app, menu_path } = cmd.args;
    return `${app}: ${(menu_path ?? []).join(" > ")}`.trim();
  }
  const label = cmd.action.replace(/_/g, " ");
  const target = cmd.args.target ?? cmd.args.path ?? "";
  return `${label} ${target}`.trim();
}

export default function CommandApproval({ commands, onResolved }) {
  if (commands.length === 0) return null;

  async function resolve(cmd, action) {
    try {
      const updated = await (action === "approve" ? approveCommand(cmd.id) : rejectCommand(cmd.id));
      onResolved?.(updated);
    } catch (err) {
      onResolved?.({ ...cmd, status: "error", detail: `⚠ ${err.message}` });
    }
  }

  return (
    <div className="command-approvals">
      {commands.map((cmd) => (
        <div key={cmd.id} className="command-card">
          <span className="command-text">{describe(cmd)}</span>
          <div className="command-actions">
            <button type="button" onClick={() => resolve(cmd, "approve")}>
              Approve
            </button>
            <button type="button" className="command-deny" onClick={() => resolve(cmd, "reject")}>
              Deny
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
