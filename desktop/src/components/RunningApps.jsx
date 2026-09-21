/**
 * RunningApps — a header button + dropdown listing currently running apps.
 *
 * Slice 2 of App Menu Actions (docs/proposals/menu-actions.md): "the main
 * orb window itself should show a visible list of open apps." A dropdown
 * rather than a modal like Settings, since this is meant for a quick
 * glance, not configuration — and it's not this component's job to answer
 * "what apps are open" by voice/chat, that's sidecar/brain.py's
 * _running_apps_reply(), a separate path through the normal chat pipeline.
 *
 * Fetches fresh on every open rather than polling continuously — the list
 * only needs to be current when someone's actually looking at it.
 */
import { useState } from "react";
import { getRunningApps } from "../api.js";

export default function RunningApps() {
  const [open, setOpen] = useState(false);
  const [apps, setApps] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  function toggle() {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    setLoading(true);
    setError(null);
    getRunningApps()
      .then((data) => setApps(data.apps))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  return (
    <div className="running-apps">
      <button
        className="settings-btn"
        onClick={toggle}
        aria-label="Show running apps"
        title="Running apps"
      >
        ▤
      </button>

      {open && (
        <div className="running-apps-panel">
          {loading && <p className="settings-hint">Loading…</p>}
          {error && <p className="settings-hint">⚠ {error}</p>}
          {!loading && !error && apps.length === 0 && (
            <p className="settings-hint">No open apps found.</p>
          )}
          {!loading && !error && apps.length > 0 && (
            <ul className="running-apps-list">
              {apps.map((name) => (
                <li key={name}>{name}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
