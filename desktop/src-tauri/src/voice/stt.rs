//! Speech-to-text via a local whisper.cpp model (through `whisper-rs`).
//! The model is downloaded once (via `curl` — already present on every
//! macOS install, so no HTTP client dependency is needed for a one-time
//! ~148MB fetch) and cached in `~/.rigel/models/`.

use std::path::PathBuf;
use std::sync::OnceLock;

use tauri::{AppHandle, Emitter};
use whisper_rs::{FullParams, SamplingStrategy, WhisperContext, WhisperContextParameters};

const MODEL_URL: &str = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin";
const MODEL_FILE: &str = "ggml-base.en.bin";

fn models_dir() -> Result<PathBuf, String> {
    let home = std::env::var_os("HOME")
        .map(PathBuf::from)
        .ok_or("HOME environment variable not set")?;
    let dir = home.join(".rigel").join("models");
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    Ok(dir)
}

pub fn model_path() -> Result<PathBuf, String> {
    Ok(models_dir()?.join(MODEL_FILE))
}

pub fn model_downloaded() -> bool {
    model_path().map(|p| p.exists()).unwrap_or(false)
}

fn download_model() -> Result<(), String> {
    let path = model_path()?;
    if path.exists() {
        return Ok(());
    }
    let tmp_path = path.with_extension("bin.partial");
    let status = std::process::Command::new("curl")
        .arg("-L")
        .arg("-f")
        .arg("-sS")
        .arg("-o")
        .arg(&tmp_path)
        .arg(MODEL_URL)
        .status()
        .map_err(|e| format!("Failed to run curl: {e}"))?;
    if !status.success() {
        let _ = std::fs::remove_file(&tmp_path);
        return Err("Failed to download the whisper model (check your network connection).".to_string());
    }
    std::fs::rename(&tmp_path, &path).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub fn voice_stt_model_status() -> bool {
    model_downloaded()
}

#[tauri::command]
pub fn voice_download_stt_model(app: AppHandle) -> Result<(), String> {
    let _ = app.emit(
        "voice://model-download",
        serde_json::json!({ "stage": "downloading" }),
    );
    let result = download_model();
    let _ = app.emit(
        "voice://model-download",
        serde_json::json!({ "stage": if result.is_ok() { "done" } else { "error" }, "error": result.as_ref().err() }),
    );
    result
}

static CONTEXT: OnceLock<WhisperContext> = OnceLock::new();

fn context() -> Result<&'static WhisperContext, String> {
    if let Some(ctx) = CONTEXT.get() {
        return Ok(ctx);
    }
    let path = model_path()?;
    if !path.exists() {
        return Err("Speech-to-text model not downloaded yet.".to_string());
    }
    // Replaces whisper.cpp's default per-token stdout logging with a no-op
    // (no log/tracing backend feature is enabled) — otherwise every
    // transcription floods the app's logs with internal decoder trace lines.
    whisper_rs::install_logging_hooks();
    let ctx = WhisperContext::new_with_params(&path, WhisperContextParameters::default())
        .map_err(|e| format!("Failed to load whisper model: {e}"))?;
    Ok(CONTEXT.get_or_init(|| ctx))
}

fn downmix_to_mono(samples: &[f32], channels: u16) -> Vec<f32> {
    if channels <= 1 {
        return samples.to_vec();
    }
    let channels = channels as usize;
    samples
        .chunks_exact(channels)
        .map(|frame| frame.iter().sum::<f32>() / channels as f32)
        .collect()
}

/// Simple linear-interpolation resample. Good enough for a one-shot,
/// finite utterance buffer feeding a speech model — not used anywhere
/// real-time/continuous, where quality would actually matter.
fn resample_to_16k(mono: &[f32], from_rate: u32) -> Vec<f32> {
    if from_rate == 16000 || mono.is_empty() {
        return mono.to_vec();
    }
    let ratio = 16000.0 / from_rate as f32;
    let out_len = (mono.len() as f32 * ratio) as usize;
    (0..out_len)
        .map(|i| {
            let src_pos = i as f32 / ratio;
            let idx = src_pos as usize;
            let frac = src_pos - idx as f32;
            let a = mono.get(idx).copied().unwrap_or(0.0);
            let b = mono.get(idx + 1).copied().unwrap_or(a);
            a + (b - a) * frac
        })
        .collect()
}

/// Transcribes a recorded utterance. `samples` are raw audio straight from
/// the capture stream (whatever rate/channel count the mic reported) — this
/// handles converting to the mono 16kHz f32 whisper.cpp expects.
pub fn transcribe(samples: &[f32], sample_rate: u32, channels: u16) -> Result<String, String> {
    let mono = downmix_to_mono(samples, channels);
    let audio = resample_to_16k(&mono, sample_rate);
    if audio.len() < 1600 {
        // Under ~100ms of 16kHz audio — not enough to transcribe meaningfully.
        return Ok(String::new());
    }

    let ctx = context()?;
    let mut state = ctx.create_state().map_err(|e| e.to_string())?;

    let mut params = FullParams::new(SamplingStrategy::Greedy { best_of: 1 });
    params.set_language(Some("en"));
    params.set_print_special(false);
    params.set_print_progress(false);
    params.set_print_realtime(false);
    params.set_print_timestamps(false);
    params.set_single_segment(true);
    // Short one-shot commands: no cross-call context, and stop the decoder
    // from emitting non-speech tokens ("[BLANK_AUDIO]", "(music)", …) that
    // it otherwise hallucinates over quiet or noisy input.
    params.set_no_context(true);
    params.set_suppress_blank(true);
    params.set_suppress_nst(true);

    state.full(params, &audio).map_err(|e| e.to_string())?;

    let mut text = String::new();
    let mut max_no_speech = 0.0f32;
    for segment in state.as_iter() {
        max_no_speech = max_no_speech.max(segment.no_speech_probability());
        text.push_str(&segment.to_string());
    }
    let text = text.trim().to_string();
    log::info!(
        "stt: {:.2}s audio -> {:?} (no_speech_prob={:.2})",
        audio.len() as f32 / 16000.0,
        text,
        max_no_speech
    );
    if !looks_like_speech(&text) {
        return Ok(String::new());
    }
    Ok(text)
}

/// Rejects whisper's non-speech artifacts: bracketed/parenthesised tags like
/// "[BLANK_AUDIO]", "(silence)", "[ Music ]", or output that has no letters
/// at all. Anything else is treated as a real utterance.
fn looks_like_speech(text: &str) -> bool {
    let t = text.trim();
    if t.is_empty() {
        return false;
    }
    if !t.chars().any(|c| c.is_alphanumeric()) {
        return false;
    }
    // Strip every [...] / (...) / *...* / ♪...♪ group; if nothing with
    // letters survives, it was all annotation.
    let mut remaining = String::new();
    let mut depth = 0usize;
    let mut in_star = false;
    for c in t.chars() {
        match c {
            '[' | '(' => depth += 1,
            ']' | ')' => depth = depth.saturating_sub(1),
            '*' | '♪' => in_star = !in_star,
            _ if depth == 0 && !in_star => remaining.push(c),
            _ => {}
        }
    }
    remaining.chars().any(|c| c.is_alphanumeric())
}

#[cfg(test)]
mod tests {
    use super::looks_like_speech;

    #[test]
    fn rejects_non_speech_tags() {
        for s in ["[BLANK_AUDIO]", "(silence)", "[ Silence ]", "(blank)", "[MUSIC]", "*inaudible*", "♪ ♪", "...", ""] {
            assert!(!looks_like_speech(s), "{s:?} should be rejected");
        }
    }

    #[test]
    fn accepts_real_speech() {
        for s in ["Open Safari", "1, 2, 3.", "(laughs) open safari", "what's the time"] {
            assert!(looks_like_speech(s), "{s:?} should be accepted");
        }
    }
}
