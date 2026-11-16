/**
 * ToolBoxSettings — Settings → Brain → ToolBox section (mockup v1, scene 4).
 * Whether the brain may find and run ToolBox tools, where ToolBox is
 * (auto-found from ~/.toolbox/service.json unless overridden), live status,
 * and the per-reply tool-step cap. No approval timeout setting: Rigel waits
 * as long as the card is up (Tony, 2026-11-15).
 */
import { useEffect, useState } from "react";
import { getToolboxConfig, saveToolboxConfig, getToolboxStatus } from "../api.js";

const DEFAULT = { enabled: true, url: null, max_steps: 5 };

function statusLine(st) {
  if (!st) return { cls: "", text: "Checking…" };
  if (st.state === "connected")
    return { cls: "ok", text: `● connected · ${st.servers} servers · ${st.tools} tools · ${st.url}` };
  if (st.state === "disabled") return { cls: "", text: "Off" };
  return { cls: "warn", text: `● offline at ${st.url}. Start it with: toolbox serve` };
}

function brainLine(brain) {
  if (!brain) return null;
  if (brain.provider === "claude") return { cls: "ok", text: "Claude can use ToolBox tools." };
  if (brain.provider === "ollama")
    return brain.tools
      ? { cls: "ok", text: `${brain.model} supports tool calling.` }
      : { cls: "warn", text: `${brain.model || "This model"} doesn't support tool calling; Rigel answers without tools.` };
  return { cls: "warn", text: "The Basic brain can't use tools. Pick Claude or Ollama above." };
}

export default function ToolBoxSettings({ open }) {
  const [config, setConfig] = useState(DEFAULT);
  const [status, setStatus] = useState(null);
  const [saveState, setSaveState] = useState(null);

  useEffect(() => {
    if (!open) return;
    getToolboxConfig().then((c) => setConfig({ ...DEFAULT, ...c })).catch(() => {});
    getToolboxStatus().then(setStatus).catch(() => setStatus({ state: "offline", url: "sidecar" }));
  }, [open]);

  async function save() {
    setSaveState("saving");
    try {
      await saveToolboxConfig({ ...config, url: config.url || null });
      setSaveState("saved");
      setStatus(await getToolboxStatus());
    } catch {
      setSaveState("error");
    }
  }

  const st = statusLine(status);
  const br = brainLine(status?.brain);

  return (
    <div className="toolbox-settings">
      <h4 className="settings-subhead">ToolBox</h4>
      <label className="provider-option">
        <input
          type="checkbox"
          checked={config.enabled}
          onChange={(e) => setConfig({ ...config, enabled: e.target.checked })}
        />
        Use ToolBox tools: let the brain find and run tools through ToolBox
      </label>
      <p className={`settings-hint ${st.cls}`}>{st.text}</p>
      {br && <p className={`settings-hint ${br.cls}`}>{br.text}</p>}
      <div className="settings-row">
        <label>Address:</label>
        <input
          type="text"
          placeholder="auto (from ~/.toolbox/service.json)"
          value={config.url || ""}
          onChange={(e) => setConfig({ ...config, url: e.target.value })}
        />
      </div>
      <div className="settings-row">
        <label>Max steps:</label>
        <select
          value={config.max_steps}
          onChange={(e) => setConfig({ ...config, max_steps: Number(e.target.value) })}
        >
          {[3, 5, 8, 10, 15].map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
      </div>
      <p className="settings-hint">
        Approvals wait until you answer, by clicking or by voice. A server can still stop waiting on its
        own: osa-system gives up after 2 minutes.
      </p>
      <div className="settings-save-row">
        <button className="settings-save-btn" onClick={save} disabled={saveState === "saving"}>
          {saveState === "saving" ? "Saving…" : "Save ToolBox"}
        </button>
        {saveState === "saved" && <span className="settings-hint ok">Saved.</span>}
        {saveState === "error" && <span className="settings-hint warn">Failed to save.</span>}
      </div>
    </div>
  );
}
