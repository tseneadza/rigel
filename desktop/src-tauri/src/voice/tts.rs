//! Text-to-speech via macOS's built-in `say`. No new dependencies, no
//! network — matches the "local execution engine" ethos and gives Rigel a
//! spoken voice with zero setup.

use std::process::{Child, Command};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use tauri::{AppHandle, Emitter, State};

/// The currently-speaking child process, if any. A new `voice_speak` call
/// kills whatever's in here before starting the next utterance, so replies
/// never overlap.
#[derive(Default)]
pub struct TtsState(pub Arc<Mutex<Option<Child>>>);

fn stop_current(state: &TtsState) {
    if let Ok(mut guard) = state.0.lock() {
        if let Some(mut child) = guard.take() {
            let _ = child.kill();
            let _ = child.wait();
            super::tts_finished();
        }
    }
}

#[tauri::command]
pub fn voice_speak(
    app: AppHandle,
    state: State<TtsState>,
    text: String,
    voice: Option<String>,
) -> Result<(), String> {
    stop_current(&state);

    let text = text.trim().to_string();
    if text.is_empty() {
        return Ok(());
    }

    let mut cmd = Command::new("/usr/bin/say");
    if let Some(v) = voice.as_deref().filter(|v| !v.is_empty()) {
        cmd.arg("-v").arg(v);
    }
    cmd.arg(&text);

    // Deafen the wake-word listener *before* audio starts coming out of the
    // speakers, not after.
    super::tts_started();
    let child = match cmd.spawn() {
        Ok(c) => c,
        Err(e) => {
            super::tts_finished();
            return Err(format!("failed to start `say`: {e}"));
        }
    };

    {
        let mut guard = state.0.lock().map_err(|e| e.to_string())?;
        *guard = Some(child);
    }
    let _ = app.emit("voice://state", serde_json::json!({ "state": "speaking" }));

    // Poll for completion on a background thread rather than blocking the
    // command (and thus the frontend's invoke() call) on the full utterance.
    let mutex = state.0.clone();
    let app_for_thread = app.clone();
    std::thread::spawn(move || loop {
        std::thread::sleep(Duration::from_millis(150));
        let mut guard = match mutex.lock() {
            Ok(g) => g,
            Err(_) => return,
        };
        match guard.as_mut() {
            Some(child) => match child.try_wait() {
                Ok(Some(_)) | Err(_) => {
                    *guard = None;
                    drop(guard);
                    super::tts_finished();
                    let _ = app_for_thread
                        .emit("voice://state", serde_json::json!({ "state": "idle" }));
                    return;
                }
                Ok(None) => continue,
            },
            // Slot was cleared by a newer voice_speak/voice_stop_speaking call;
            // that call owns emitting the next state, so this thread is done.
            None => return,
        }
    });

    Ok(())
}

#[tauri::command]
pub fn voice_stop_speaking(app: AppHandle, state: State<TtsState>) -> Result<(), String> {
    stop_current(&state);
    let _ = app.emit("voice://state", serde_json::json!({ "state": "idle" }));
    Ok(())
}

/// Installed macOS voice names (`say -v ?`), for the Settings voice picker.
#[tauri::command]
pub fn voice_list_tts_voices() -> Result<Vec<String>, String> {
    let output = Command::new("/usr/bin/say")
        .arg("-v")
        .arg("?")
        .output()
        .map_err(|e| format!("failed to list voices: {e}"))?;
    let text = String::from_utf8_lossy(&output.stdout);
    let mut voices: Vec<String> = text
        .lines()
        .filter_map(|line| line.split_whitespace().next().map(str::to_string))
        .collect();
    voices.sort();
    voices.dedup();
    Ok(voices)
}
