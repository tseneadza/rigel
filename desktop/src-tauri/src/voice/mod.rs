//! Rigel's voice pipeline. Lives entirely in the native process — the
//! sidecar only ever sees final text, exactly like typed input.

pub mod capture;
pub mod enroll;
pub mod listener;
pub mod stt;
pub mod tts;

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{AppHandle, State};

/// Shared "Rigel is talking" gate between TTS and the wake-word listener.
///
/// The microphone hears the speakers. Without this, every spoken reply is
/// fed straight back into the wake-word detector, which can trip on it,
/// record the silence after the reply ends, transcribe that as
/// "[BLANK_AUDIO]", send it to the brain, speak the reply… and loop.
pub struct SpeechGate {
    speaking: AtomicBool,
    ended_at: Mutex<Option<Instant>>,
}

/// How long after `say` finishes the listener stays deaf — covers speaker
/// tail/reverb and the TTS process teardown lag.
const POST_SPEECH_COOLDOWN: Duration = Duration::from_millis(700);

static SPEECH_GATE: SpeechGate = SpeechGate {
    speaking: AtomicBool::new(false),
    ended_at: Mutex::new(None),
};

pub fn tts_started() {
    SPEECH_GATE.speaking.store(true, Ordering::SeqCst);
}

pub fn tts_finished() {
    if let Ok(mut g) = SPEECH_GATE.ended_at.lock() {
        *g = Some(Instant::now());
    }
    SPEECH_GATE.speaking.store(false, Ordering::SeqCst);
}

/// True while Rigel is speaking, and for a short cooldown afterwards.
pub fn tts_blocks_listening() -> bool {
    if SPEECH_GATE.speaking.load(Ordering::SeqCst) {
        return true;
    }
    SPEECH_GATE
        .ended_at
        .lock()
        .ok()
        .and_then(|g| *g)
        .map(|t| t.elapsed() < POST_SPEECH_COOLDOWN)
        .unwrap_or(false)
}

/// Holds the running listener thread's stop handle, if voice is enabled.
#[derive(Default)]
pub struct ListenerState(pub Mutex<Option<listener::ListenerHandle>>);

#[tauri::command]
pub fn voice_set_enabled(app: AppHandle, state: State<ListenerState>, enabled: bool) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    if enabled {
        if guard.is_some() {
            return Ok(());
        }
        *guard = Some(listener::start(app)?);
    } else if let Some(handle) = guard.take() {
        handle.stop();
    }
    Ok(())
}

#[tauri::command]
pub fn voice_is_enabled(state: State<ListenerState>) -> bool {
    state.0.lock().map(|g| g.is_some()).unwrap_or(false)
}
