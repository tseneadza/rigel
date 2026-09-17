/**
 * Thin client for Rigel's native voice pipeline (Tauri commands + events).
 * No-ops outside a Tauri webview (plain browser/dev preview), matching the
 * pattern in nativeWindow.js and hotkey.js.
 */
const isTauri = () => typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

/**
 * Subscribes via `subscribe(cb)` (which resolves to an unlisten fn) inside a
 * React effect, safely: if the effect is torn down before the subscription
 * promise resolves — which React StrictMode and Vite HMR do routinely — the
 * late-arriving unlisten is invoked immediately instead of leaking a second
 * live listener that would double-fire every event.
 */
export function subscribeInEffect(subscribe, callback) {
  let cancelled = false;
  let unlisten = null;
  subscribe(callback)
    .then((fn) => {
      if (cancelled) fn?.();
      else unlisten = fn;
    })
    .catch((err) => console.error("voice event subscription failed:", err));
  return () => {
    cancelled = true;
    unlisten?.();
  };
}

/**
 * Whisper's non-speech artifacts ("[BLANK_AUDIO]", "(silence)", "[ Music ]",
 * or punctuation-only output). The native side already filters these; this is
 * a backstop so nothing like it can ever reach the chat backend or the TTS.
 */
export function looksLikeSpeech(text) {
  const t = (text ?? "").trim();
  if (!t) return false;
  const stripped = t.replace(/\[[^\]]*\]|\([^)]*\)|\*[^*]*\*|♪[^♪]*♪/g, "");
  return /[\p{L}\p{N}]/u.test(stripped);
}

export async function speak(text, voice) {
  if (!isTauri() || !text?.trim()) return;
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("voice_speak", { text, voice: voice || null });
}

export async function stopSpeaking() {
  if (!isTauri()) return;
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("voice_stop_speaking");
}

export async function listTtsVoices() {
  if (!isTauri()) return [];
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("voice_list_tts_voices");
}

/** Subscribes to voice://state events ({state: "idle"|"speaking"|...}). Returns an unlisten fn. */
export async function onVoiceState(callback) {
  if (!isTauri()) return () => {};
  const { listen } = await import("@tauri-apps/api/event");
  return listen("voice://state", (event) => callback(event.payload));
}

/** Records 3 short samples of the wake phrase and builds+saves the wakeword model. */
export async function enrollWakeword() {
  if (!isTauri()) {
    throw new Error("Voice features require the packaged desktop app.");
  }
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("voice_enroll_wakeword");
}

export async function getWakewordStatus() {
  if (!isTauri()) return false;
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("voice_wakeword_status");
}

export async function clearWakeword() {
  if (!isTauri()) return;
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("voice_clear_wakeword");
}

/** Subscribes to voice://enroll-progress events ({stage, index, total}). Returns an unlisten fn. */
export async function onEnrollProgress(callback) {
  if (!isTauri()) return () => {};
  const { listen } = await import("@tauri-apps/api/event");
  return listen("voice://enroll-progress", (event) => callback(event.payload));
}

export async function getSttModelStatus() {
  if (!isTauri()) return false;
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("voice_stt_model_status");
}

/** Downloads the ~148MB whisper model (one-time). */
export async function downloadSttModel() {
  if (!isTauri()) {
    throw new Error("Voice features require the packaged desktop app.");
  }
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("voice_download_stt_model");
}

/** Subscribes to voice://model-download events ({stage, error?}). Returns an unlisten fn. */
export async function onModelDownload(callback) {
  if (!isTauri()) return () => {};
  const { listen } = await import("@tauri-apps/api/event");
  return listen("voice://model-download", (event) => callback(event.payload));
}

/** Starts/stops always-on wake-word listening. Throws if wake word/model aren't set up yet. */
export async function setVoiceEnabled(enabled) {
  if (!isTauri()) {
    if (enabled) throw new Error("Voice features require the packaged desktop app.");
    return;
  }
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("voice_set_enabled", { enabled });
}

export async function isVoiceEnabled() {
  if (!isTauri()) return false;
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke("voice_is_enabled");
}

/** Subscribes to voice://transcript events ({text}). Returns an unlisten fn. */
export async function onTranscript(callback) {
  if (!isTauri()) return () => {};
  const { listen } = await import("@tauri-apps/api/event");
  return listen("voice://transcript", (event) => callback(event.payload));
}

/** Subscribes to voice://error events ({message}). Returns an unlisten fn. */
export async function onVoiceError(callback) {
  if (!isTauri()) return () => {};
  const { listen } = await import("@tauri-apps/api/event");
  return listen("voice://error", (event) => callback(event.payload));
}
