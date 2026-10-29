/**
 * WhitelistSettings — per-action auto-approve rules for the execution layer.
 *
 * A whitelisted command (action set to "all", or its specific target listed)
 * runs the moment it's detected, with no approval card. Everything else
 * still lands in the pending queue as before. Mirrors the shape of the
 * sidecar's `whitelist_config` setting: `{action: {all, targets}}`.
 *
 * Per-app handler actions (`sidecar/handlers/`) get their own section below
 * the four fixed actions, since `config.app_action` is keyed by app_id
 * rather than being one of the four fixed action names — an app's tool list
 * isn't known statically, so it's fetched from `GET /handlers` at mount.
 */
import { useEffect, useState } from "react";
import { getHandlers } from "../api.js";

const ACTIONS = [
  { key: "open_app", label: "Open app", placeholder: "App name, e.g. Chrome" },
  { key: "close_app", label: "Close app", placeholder: "App name, e.g. Slack" },
  { key: "create_file", label: "Create file", placeholder: "Path, e.g. notes.txt" },
  { key: "delete_file", label: "Delete file", placeholder: "Path, e.g. notes.txt" },
];

export default function WhitelistSettings({ config, onChange }) {
  const [drafts, setDrafts] = useState({});
  const [handlers, setHandlers] = useState([]);

  useEffect(() => {
    getHandlers()
      .then((data) => setHandlers(data.handlers))
      .catch(() => setHandlers([])); // sidecar unreachable — just hide the section
  }, []);

  function entryFor(key) {
    return config[key] || { all: false, targets: [] };
  }

  function appEntryFor(appId) {
    return (config.app_action || {})[appId] || { all: false, tools: [] };
  }

  function toggleAppAll(appId, checked) {
    onChange({
      ...config,
      app_action: { ...config.app_action, [appId]: { ...appEntryFor(appId), all: checked } },
    });
  }

  function toggleAppTool(appId, tool, checked) {
    const current = appEntryFor(appId).tools;
    const tools = checked ? [...current, tool] : current.filter((t) => t !== tool);
    onChange({
      ...config,
      app_action: { ...config.app_action, [appId]: { ...appEntryFor(appId), tools } },
    });
  }

  function toggleAll(key, checked) {
    onChange({ ...config, [key]: { ...entryFor(key), all: checked } });
  }

  function addTarget(key) {
    const value = (drafts[key] || "").trim();
    setDrafts((d) => ({ ...d, [key]: "" }));
    if (!value) return;
    const targets = entryFor(key).targets;
    if (targets.some((t) => t.toLowerCase() === value.toLowerCase())) return;
    onChange({ ...config, [key]: { ...entryFor(key), targets: [...targets, value] } });
  }

  function removeTarget(key, target) {
    const targets = entryFor(key).targets.filter((t) => t !== target);
    onChange({ ...config, [key]: { ...entryFor(key), targets } });
  }

  return (
    <div className="whitelist-settings">
      <p className="settings-hint">
        Whitelisted commands run immediately — no approval card, no waiting. Everything
        else still stops for your Approve/Deny.
      </p>

      {ACTIONS.map(({ key, label, placeholder }) => {
        const entry = entryFor(key);
        return (
          <div key={key} className="whitelist-action">
            <label className="provider-option">
              <input type="checkbox" checked={entry.all} onChange={(e) => toggleAll(key, e.target.checked)} />
              Allow all — {label.toLowerCase()}
            </label>

            {!entry.all && (
              <>
                <div className="settings-row">
                  <input
                    type="text"
                    placeholder={placeholder}
                    value={drafts[key] || ""}
                    onChange={(e) => setDrafts((d) => ({ ...d, [key]: e.target.value }))}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addTarget(key);
                      }
                    }}
                  />
                  <button type="button" className="reset-btn" onClick={() => addTarget(key)}>
                    Add
                  </button>
                </div>

                {entry.targets.length > 0 && (
                  <div className="whitelist-chips">
                    {entry.targets.map((t) => (
                      <span key={t} className="whitelist-chip">
                        {t}
                        <button type="button" onClick={() => removeTarget(key, t)} aria-label={`Remove ${t}`}>
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        );
      })}

      {handlers.length > 0 && (
        <>
          <p className="settings-hint">
            Per-app actions (from Rigel's app handlers) — each app whitelists independently.
          </p>
          {handlers.map(({ app_id, display_name, tools }) => {
            const entry = appEntryFor(app_id);
            return (
              <div key={app_id} className="whitelist-action">
                <label className="provider-option">
                  <input
                    type="checkbox"
                    checked={entry.all}
                    onChange={(e) => toggleAppAll(app_id, e.target.checked)}
                  />
                  Allow all — {display_name}
                </label>

                {!entry.all && tools.length > 0 && (
                  <div className="whitelist-chips">
                    {tools.map(({ name }) => (
                      <label key={name} className="provider-option">
                        <input
                          type="checkbox"
                          checked={entry.tools.includes(name)}
                          onChange={(e) => toggleAppTool(app_id, name, e.target.checked)}
                        />
                        {name.replace(/_/g, " ")}
                      </label>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}
