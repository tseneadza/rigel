/**
 * SettingsPanel — modal overlay with two tabs: Orb (size/position, moved
 * here from the console) and Brain (LLM provider: stub / Claude / Ollama).
 */
import { useEffect, useState } from "react";
import ResizeControl from "./ResizeControl.jsx";
import { getLlmConfig, saveLlmConfig, getLlmOptions } from "../api.js";

const DEFAULT_LLM_CONFIG = {
  provider: "stub",
  claude_model: null,
  ollama_model: null,
  ollama_host: "http://localhost:11434",
};

const FIT_LABEL = {
  comfortable: "✅ fits comfortably",
  borderline: "⚠ may run slowly",
  too_large: "❌ not recommended on this machine",
  unknown: "— fit unknown",
};

export default function SettingsPanel({ open, onClose, orbConfig, onOrbConfigChange }) {
  const [tab, setTab] = useState("orb");
  const [llmConfig, setLlmConfig] = useState(DEFAULT_LLM_CONFIG);
  const [llmOptions, setLlmOptions] = useState(null);
  const [hostInput, setHostInput] = useState(DEFAULT_LLM_CONFIG.ollama_host);
  const [loading, setLoading] = useState(false);
  const [saveState, setSaveState] = useState(null); // null | "saving" | "saved" | "error"

  function loadAll(ollamaHost) {
    setLoading(true);
    Promise.all([getLlmConfig(), getLlmOptions(ollamaHost)])
      .then(([config, options]) => {
        setLlmConfig(config);
        setHostInput(config.ollama_host || DEFAULT_LLM_CONFIG.ollama_host);
        setLlmOptions(options);
      })
      .catch(() => setLlmOptions(null))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (open) {
      setSaveState(null);
      loadAll();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    function onKey(e) {
      if (e.key === "Escape") onClose?.();
    }
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  function updateLlmConfig(patch) {
    setLlmConfig((prev) => ({ ...prev, ...patch }));
  }

  async function save() {
    setSaveState("saving");
    try {
      await saveLlmConfig(llmConfig);
      setSaveState("saved");
    } catch (err) {
      console.error("Failed to save LLM config:", err);
      setSaveState("error");
    }
  }

  const claude = llmOptions?.claude;
  const ollama = llmOptions?.ollama;

  return (
    <div className="settings-overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose?.()}>
      <div className="settings-panel">
        <div className="settings-header">
          <span className="settings-title">Settings</span>
          <button className="settings-close" onClick={onClose} aria-label="Close settings">
            ✕
          </button>
        </div>

        <div className="settings-tabs">
          <button
            className={`settings-tab ${tab === "orb" ? "active" : ""}`}
            onClick={() => setTab("orb")}
          >
            Orb
          </button>
          <button
            className={`settings-tab ${tab === "brain" ? "active" : ""}`}
            onClick={() => setTab("brain")}
          >
            Brain
          </button>
        </div>

        <div className="settings-body">
          {tab === "orb" && orbConfig && onOrbConfigChange && (
            <ResizeControl orbConfig={orbConfig} onConfigChange={onOrbConfigChange} />
          )}

          {tab === "brain" && (
            <div className="brain-settings">
              {loading && <p className="settings-hint">Loading…</p>}

              <div className="provider-row">
                <label className="provider-option">
                  <input
                    type="radio"
                    name="provider"
                    checked={llmConfig.provider === "stub"}
                    onChange={() => updateLlmConfig({ provider: "stub" })}
                  />
                  Basic (pattern matching, no LLM)
                </label>
                <label className="provider-option">
                  <input
                    type="radio"
                    name="provider"
                    checked={llmConfig.provider === "claude"}
                    onChange={() => updateLlmConfig({ provider: "claude" })}
                  />
                  Claude
                </label>
                <label className="provider-option">
                  <input
                    type="radio"
                    name="provider"
                    checked={llmConfig.provider === "ollama"}
                    onChange={() => updateLlmConfig({ provider: "ollama" })}
                  />
                  Ollama (local)
                </label>
              </div>

              {llmConfig.provider === "claude" && claude && (
                <div className="provider-detail">
                  <div className="settings-row">
                    <label>Model:</label>
                    <select
                      value={llmConfig.claude_model || ""}
                      onChange={(e) => updateLlmConfig({ claude_model: e.target.value })}
                    >
                      <option value="" disabled>
                        Choose a model…
                      </option>
                      {claude.models.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  </div>
                  <p className={`settings-hint ${claude.api_key_configured ? "ok" : "warn"}`}>
                    {claude.api_key_configured
                      ? "✅ ANTHROPIC_API_KEY is configured."
                      : "⚠ ANTHROPIC_API_KEY is not set. Export it in the environment Rigel's sidecar runs in, then restart the sidecar."}
                  </p>
                </div>
              )}

              {llmConfig.provider === "ollama" && (
                <div className="provider-detail">
                  <div className="settings-row">
                    <label>Host:</label>
                    <input
                      type="text"
                      value={hostInput}
                      onChange={(e) => setHostInput(e.target.value)}
                    />
                    <button
                      className="reset-btn"
                      onClick={() => {
                        updateLlmConfig({ ollama_host: hostInput });
                        loadAll(hostInput);
                      }}
                    >
                      Refresh
                    </button>
                  </div>

                  {ollama && (
                    <p className="settings-hint">System RAM: {ollama.system_ram_gb} GB</p>
                  )}

                  {ollama && !ollama.installed && ollama.binary_present && (
                    <p className="settings-hint warn">
                      ⚠ Ollama is installed but not reachable at {ollama.host}. Start it (
                      <span className="settings-mono">ollama serve</span>) and hit Refresh.
                    </p>
                  )}

                  {ollama && !ollama.installed && !ollama.binary_present && (
                    <p className="settings-hint warn">
                      ⚠ Ollama not detected. Install it from{" "}
                      <span className="settings-mono">ollama.com</span>, pull a model (e.g.{" "}
                      <span className="settings-mono">ollama pull llama3.2:3b</span>), then hit
                      Refresh.
                    </p>
                  )}

                  {ollama && ollama.installed && ollama.models.length === 0 && (
                    <p className="settings-hint warn">
                      ⚠ Ollama is running but no models are pulled yet. Run{" "}
                      <span className="settings-mono">ollama pull llama3.2:3b</span> and hit
                      Refresh.
                    </p>
                  )}

                  {ollama && ollama.installed && ollama.models.length > 0 && (
                    <div className="ollama-model-list">
                      {ollama.models.map((m) => (
                        <label key={m.name} className="provider-option ollama-model-row">
                          <input
                            type="radio"
                            name="ollama_model"
                            checked={llmConfig.ollama_model === m.name}
                            onChange={() => updateLlmConfig({ ollama_model: m.name })}
                          />
                          <span className="settings-mono">{m.name}</span>
                          <span className="settings-hint">
                            {m.size_gb} GB — {FIT_LABEL[m.fit]}
                          </span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="settings-save-row">
                <button className="settings-save-btn" onClick={save} disabled={saveState === "saving"}>
                  {saveState === "saving" ? "Saving…" : "Save"}
                </button>
                {saveState === "saved" && <span className="settings-hint ok">Saved.</span>}
                {saveState === "error" && <span className="settings-hint warn">Failed to save.</span>}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
