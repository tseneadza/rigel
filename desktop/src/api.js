// Thin client for the Rigel sidecar. Base URL is overridable at build time
// via VITE_RIGEL_API so the packaged Tauri app and dev server can differ.
const BASE = import.meta.env.VITE_RIGEL_API || "http://localhost:5131";

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
export const sendChat = (text) =>
  req("/api/rigel/chat", { method: "POST", body: JSON.stringify({ text }) });
