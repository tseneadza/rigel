// Thin client for the Rigel sidecar. Base URL is overridable at build time
// via VITE_RIGEL_API so the packaged Tauri app and dev server can differ.
const BASE = import.meta.env.VITE_RIGEL_API || "http://localhost:5140";

async function req(path, opts) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

export const getState = () => req("/api/rigel/state");
export const getLogs = (limit = 50) => req(`/api/rigel/logs?limit=${limit}`);
export const getHandlers = () => req("/api/rigel/handlers");
export const getRunningApps = () => req("/api/rigel/running-apps");
export const sendChat = (text) =>
  req("/api/rigel/chat", { method: "POST", body: JSON.stringify({ text }) });
export const approveCommand = (id) =>
  req(`/api/rigel/commands/${id}/approve`, { method: "POST" });
export const rejectCommand = (id) =>
  req(`/api/rigel/commands/${id}/reject`, { method: "POST" });
export const getOrbConfig = () => req("/api/rigel/settings/orb-config");
export const saveOrbConfig = (config) =>
  req("/api/rigel/settings/orb-config", {
    method: "POST",
    body: JSON.stringify(config),
  });
export const getLlmConfig = () => req("/api/rigel/settings/llm-config");
export const saveLlmConfig = (config) =>
  req("/api/rigel/settings/llm-config", {
    method: "POST",
    body: JSON.stringify(config),
  });
export const getLlmOptions = (ollamaHost) =>
  req(
    `/api/rigel/settings/llm-options${
      ollamaHost ? `?ollama_host=${encodeURIComponent(ollamaHost)}` : ""
    }`
  );
export const getVoiceConfig = () => req("/api/rigel/settings/voice-config");
export const saveVoiceConfig = (config) =>
  req("/api/rigel/settings/voice-config", {
    method: "POST",
    body: JSON.stringify(config),
  });
export const getWhitelistConfig = () => req("/api/rigel/settings/whitelist-config");
export const saveWhitelistConfig = (config) =>
  req("/api/rigel/settings/whitelist-config", {
    method: "POST",
    body: JSON.stringify(config),
  });
