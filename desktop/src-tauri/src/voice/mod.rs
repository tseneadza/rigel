//! Rigel's voice pipeline. Lives entirely in the native process — the
//! sidecar only ever sees final text, exactly like typed input.

pub mod capture;
pub mod enroll;
pub mod embedding;
pub mod fbank;
pub mod listener;
pub mod speaker;
pub mod model;
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

/// "Record the next utterance without waiting for the wake word" — set by
/// `voice_listen_once` (a ToolBox approval wants a spoken yes/no), consumed
/// by the listener the next time it's listening and not muted by TTS, so
/// it's safe to set while Rigel is still speaking the question.
static LISTEN_ONCE: AtomicBool = AtomicBool::new(false);

pub fn take_listen_once() -> bool {
    let take = LISTEN_ONCE.swap(false, Ordering::SeqCst);
    if take {
        // A fresh listen-once starts clean: no stale cancel from an earlier one.
        CANCEL_LISTEN_ONCE.store(false, Ordering::SeqCst);
    }
    take
}

/// Set when the approval a listen-once was for has been answered another
/// way (a click) or has gone away. Consumed by a listen-once recording in
/// progress, which is then dropped instead of being transcribed. Live bug
/// (2026-11-22): Tony clicked Approve, the recording kept running, captured
/// Rigel's own spoken reply, and fed it back in as if Tony had said it.
static CANCEL_LISTEN_ONCE: AtomicBool = AtomicBool::new(false);

pub fn take_cancel_listen_once() -> bool {
    CANCEL_LISTEN_ONCE.swap(false, Ordering::SeqCst)
}

/// "Rigel's ears" muted (P2, FR-18). Silences only the wake word: a ToolBox
/// approval can still be answered by voice (listen-once above). The desktop
/// UI sets it, and syncs it from the sidecar setting on launch.
static WAKE_WORD_MUTED: AtomicBool = AtomicBool::new(false);

pub fn wake_word_muted() -> bool {
    WAKE_WORD_MUTED.load(Ordering::SeqCst)
}

#[tauri::command]
pub fn voice_set_wake_word_muted(muted: bool) {
    WAKE_WORD_MUTED.store(muted, Ordering::SeqCst);
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

#[tauri::command]
pub fn voice_listen_once(state: State<ListenerState>) -> Result<(), String> {
    let running = state.0.lock().map(|g| g.is_some()).unwrap_or(false);
    if !running {
        return Err("Voice listening is off. Turn it on in Settings → Voice.".to_string());
    }
    LISTEN_ONCE.store(true, Ordering::SeqCst);
    Ok(())
}

#[cfg(test)]
mod wake_mute_tests {
    use super::*;

    #[test]
    fn wake_word_mute_flag_round_trips() {
        voice_set_wake_word_muted(true);
        assert!(wake_word_muted());
        voice_set_wake_word_muted(false);
        assert!(!wake_word_muted());
    }
}

/// Cancel a pending or in-progress listen-once (the approval was answered by
/// click, or is no longer waiting). Harmless when nothing is pending.
#[tauri::command]
pub fn voice_cancel_listen_once() -> Result<(), String> {
    LISTEN_ONCE.store(false, Ordering::SeqCst);
    CANCEL_LISTEN_ONCE.store(true, Ordering::SeqCst);
    Ok(())
}
