/**
 * WhitelistSettings — per-action auto-approve rules for the execution layer.
 *
 * A whitelisted command (action set to "all", or its specific target listed)
 * runs the moment it's detected, with no approval card. Everything else
 * still lands in the pending queue as before. Mirrors the shape of the
 * sidecar's `whitelist_config` setting: `{action: {all, targets}}`.
 */
import { useState } from "react";

const ACTIONS = [
  { key: "open_app", label: "Open app", placeholder: "App name, e.g. Chrome" },
  { key: "close_app", label: "Close app", placeholder: "App name, e.g. Slack" },
  { key: "create_file", label: "Create file", placeholder: "Path, e.g. notes.txt" },
  { key: "delete_file", label: "Delete file", placeholder: "Path, e.g. notes.txt" },
];

export default function WhitelistSettings({ config, onChange }) {
  const [drafts, setDrafts] = useState({});

  function entryFor(key) {
    return config[key] || { all: false, targets: [] };
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
    </div>
  );
}
