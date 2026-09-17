/**
 * SettingsPanel — modal overlay with two tabs: Orb (size/position, moved
 * here from the console) and Brain (LLM provider: stub / Claude / Ollama).
 */
import { useEffect, useState } from "react";
import ResizeControl from "./ResizeControl.jsx";
import { getLlmConfig, saveLlmConfig, getLlmOptions, getVoiceConfig, saveVoiceConfig } from "../api.js";
import {
  listTtsVoices,
  speak,
  enrollWakeword,
  getWakewordStatus,
  clearWakeword,
  onEnrollProgress,
  getSttModelStatus,
  downloadSttModel,
  onModelDownload,
  setVoiceEnabled,
  isVoiceEnabled,
  subscribeInEffect,
} from "../voice.js";

const DEFAULT_LLM_CONFIG = {
  provider: "stub",
  claude_model: null,
  ollama_model: null,
  ollama_host: "http://localhost:11434",
};

const DEFAULT_VOICE_CONFIG = {
  tts_voice: null,
  speak_typed_replies: false,
  enabled: false,
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
  const [voiceConfig, setVoiceConfig] = useState(DEFAULT_VOICE_CONFIG);
  const [ttsVoices, setTtsVoices] = useState([]);
  const [voiceSaveState, setVoiceSaveState] = useState(null); // null | "saving" | "saved" | "error"
  const [wakewordTrained, setWakewordTrained] = useState(false);
  const [enrollState, setEnrollState] = useState(null); // null | {stage, index, total} | {stage:"error", message}
  const [sttModelReady, setSttModelReady] = useState(false);
  const [modelDownload, setModelDownload] = useState(null); // null | {stage, error?}
  const [voiceEnableError, setVoiceEnableError] = useState(null);

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
    if (!open) return;
    setVoiceSaveState(null);
    setEnrollState(null);
    setVoiceEnableError(null);
    // Show the checkbox as the listener actually *is*, not as the saved
    // config says: the toggle applies immediately (below), so the two can
    // disagree, and silently displaying "off" over a running listener left
    // the mic live with no indication.
    Promise.all([getVoiceConfig(), isVoiceEnabled().catch(() => null)])
      .then(([config, actuallyEnabled]) => {
        setVoiceConfig(
          actuallyEnabled === null ? config : { ...config, enabled: actuallyEnabled }
        );
      })
      .catch(() => {});
    listTtsVoices().then(setTtsVoices).catch(() => setTtsVoices([]));
    getWakewordStatus().then(setWakewordTrained).catch(() => setWakewordTrained(false));
    getSttModelStatus().then(setSttModelReady).catch(() => setSttModelReady(false));
  }, [open]);

  useEffect(
    () =>
      subscribeInEffect(onModelDownload, (payload) => {
        setModelDownload(payload);
        if (payload.stage === "done") setSttModelReady(true);
      }),
    []
  );

  async function startModelDownload() {
    setModelDownload({ stage: "downloading" });
    try {
      await downloadSttModel();
    } catch (err) {
      setModelDownload({ stage: "error", error: err.message });
    }
  }

  async function toggleVoiceEnabled(checked) {
    updateVoiceConfig({ enabled: checked });
    setVoiceEnableError(null);
    try {
      await setVoiceEnabled(checked);
      // Applied immediately, so persist immediately too — otherwise closing
      // Settings without "Save" leaves the listener running but the saved
      // config (and next launch) saying it's off.
      await saveVoiceConfig({ ...voiceConfig, enabled: checked });
    } catch (err) {
      setVoiceEnableError(err.message);
      updateVoiceConfig({ enabled: false });
    }
  }

  useEffect(() => subscribeInEffect(onEnrollProgress, (payload) => setEnrollState(payload)), []);

  function updateVoiceConfig(patch) {
    setVoiceConfig((prev) => ({ ...prev, ...patch }));
  }

  async function startEnroll() {
    setEnrollState({ stage: "starting" });
    try {
      await enrollWakeword();
      setEnrollState({ stage: "done" });
      setWakewordTrained(true);
    } catch (err) {
      setEnrollState({ stage: "error", message: err.message });
    }
  }

  async function resetWakeword() {
    await clearWakeword().catch(() => {});
    setWakewordTrained(false);
    setEnrollState(null);
  }

  async function saveVoice() {
    setVoiceSaveState("saving");
    try {
      await saveVoiceConfig(voiceConfig);
      setVoiceSaveState("saved");
    } catch (err) {
      console.error("Failed to save voice config:", err);
      setVoiceSaveState("error");
    }
  }

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
          <button
            className={`settings-tab ${tab === "voice" ? "active" : ""}`}
            onClick={() => setTab("voice")}
          >
            Voice
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

          {tab === "voice" && (
            <div className="voice-settings">
              <p className="settings-hint">
                Fully local: wake-word matching runs against your own recorded phrase and
                replies are spoken with macOS's built-in voices — no network, no accounts.
              </p>

              <div className="wakeword-enroll">
                <p className="settings-hint">
                  Wake word: {wakewordTrained ? "✅ trained" : "not set up yet"}
                </p>

                {enrollState?.stage === "starting" && (
                  <p className="settings-hint">Starting…</p>
                )}
                {enrollState?.stage === "ready" && (
                  <p className="settings-hint">
                    Get ready… ({enrollState.index + 1}/{enrollState.total})
                  </p>
                )}
                {enrollState?.stage === "recording" && (
                  <p className="settings-hint ok">
                    🎙 Say your wake phrase now… ({enrollState.index + 1}/{enrollState.total})
                  </p>
                )}
                {enrollState?.stage === "done" && (
                  <p className="settings-hint ok">Wake phrase saved.</p>
                )}
                {enrollState?.stage === "error" && (
                  <p className="settings-hint warn">⚠ {enrollState.message}</p>
                )}

                <div className="settings-row">
                  <button
                    className="reset-btn"
                    onClick={startEnroll}
                    disabled={["starting", "ready", "recording"].includes(enrollState?.stage)}
                  >
                    {wakewordTrained ? "Re-record wake phrase" : "Record wake phrase"}
                  </button>
                  {wakewordTrained && (
                    <button className="reset-btn" onClick={resetWakeword}>
                      Clear
                    </button>
                  )}
                </div>
              </div>

              <div className="wakeword-enroll">
                <p className="settings-hint">
                  Speech-to-text model:{" "}
                  {sttModelReady ? "✅ downloaded" : "not downloaded yet (~148MB, one-time)"}
                </p>
                {modelDownload?.stage === "downloading" && (
                  <p className="settings-hint">Downloading…</p>
                )}
                {modelDownload?.stage === "done" && (
                  <p className="settings-hint ok">Model ready.</p>
                )}
                {modelDownload?.stage === "error" && (
                  <p className="settings-hint warn">⚠ {modelDownload.error}</p>
                )}
                {!sttModelReady && (
                  <button
                    className="reset-btn"
                    onClick={startModelDownload}
                    disabled={modelDownload?.stage === "downloading"}
                  >
                    Download model
                  </button>
                )}
              </div>

              <label className="provider-option">
                <input
                  type="checkbox"
                  checked={voiceConfig.enabled}
                  disabled={!wakewordTrained || !sttModelReady}
                  onChange={(e) => toggleVoiceEnabled(e.target.checked)}
                />
                Listen for the wake word
              </label>
              {(!wakewordTrained || !sttModelReady) && (
                <p className="settings-hint">
                  Record a wake phrase and download the model above to enable listening.
                </p>
              )}
              {voiceEnableError && <p className="settings-hint warn">⚠ {voiceEnableError}</p>}

              <label className="provider-option">
                <input
                  type="checkbox"
                  checked={voiceConfig.speak_typed_replies}
                  onChange={(e) => updateVoiceConfig({ speak_typed_replies: e.target.checked })}
                />
                Also speak replies to typed messages
              </label>

              <div className="settings-row">
                <label>Voice:</label>
                <select
                  value={voiceConfig.tts_voice || ""}
                  onChange={(e) => updateVoiceConfig({ tts_voice: e.target.value || null })}
                >
                  <option value="">System default</option>
                  {ttsVoices.map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </select>
                <button
                  className="reset-btn"
                  onClick={() => speak("Standing by.", voiceConfig.tts_voice)}
                >
                  Test
                </button>
              </div>

              {ttsVoices.length === 0 && (
                <p className="settings-hint warn">
                  ⚠ No voices found — voice playback only works in the packaged desktop app,
                  not this web preview.
                </p>
              )}

              <div className="settings-save-row">
                <button
                  className="settings-save-btn"
                  onClick={saveVoice}
                  disabled={voiceSaveState === "saving"}
                >
                  {voiceSaveState === "saving" ? "Saving…" : "Save"}
                </button>
                {voiceSaveState === "saved" && <span className="settings-hint ok">Saved.</span>}
                {voiceSaveState === "error" && (
                  <span className="settings-hint warn">Failed to save.</span>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
