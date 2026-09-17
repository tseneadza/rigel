//! Always-on wake-word listening. Runs a dedicated thread for as long as
//! voice is enabled: continuously feeds the microphone into rustpotter, and
//! on a wake-word hit, records until a short silence (or a hard time cap),
//! then hands the recording to whisper.cpp for transcription.

use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{self, RecvTimeoutError};
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use rustpotter::{Rustpotter, RustpotterConfig, RustpotterDetection};
use tauri::{AppHandle, Emitter};

use super::{enroll, stt};

/// Absolute floor for "this chunk contains speech". The live threshold is
/// `max(SPEECH_RMS_FLOOR, SPEECH_OVER_NOISE * noise_floor)` where the noise
/// floor is tracked while idle, so a quiet mic in a quiet room (idle RMS
/// ~0.0003 on the user's machine) doesn't need speech to hit a fixed 0.01.
const SPEECH_RMS_FLOOR: f32 = 0.003;
const SPEECH_OVER_NOISE: f32 = 6.0;
const NOISE_FLOOR_ALPHA: f32 = 0.05;
const SILENCE_HANGOVER: Duration = Duration::from_millis(1200);
const MAX_RECORDING: Duration = Duration::from_secs(12);
// Grace period to actually start speaking the command after the wake word
// fires — people often pause briefly after "Hey Rigel" before continuing.
// Silence during this window doesn't end the recording.
const SPEECH_ONSET_GRACE: Duration = Duration::from_millis(2500);
/// How many captured utterances to keep in ~/.rigel/debug for inspection.
const DEBUG_KEEP: usize = 12;
/// How often the idle status line is logged.
const STATUS_EVERY: Duration = Duration::from_secs(20);

pub struct ListenerHandle {
    stop_flag: Arc<AtomicBool>,
}

impl ListenerHandle {
    pub fn stop(&self) {
        self.stop_flag.store(true, Ordering::SeqCst);
    }
}

enum Mode {
    Listening,
    Recording {
        buffer: Vec<f32>,
        last_voice: Instant,
        started: Instant,
        heard_speech: bool,
        speech_threshold: f32,
        chunk_levels: Vec<f32>,
    },
}

fn rms(samples: &[f32]) -> f32 {
    if samples.is_empty() {
        return 0.0;
    }
    (samples.iter().map(|s| s * s).sum::<f32>() / samples.len() as f32).sqrt()
}

fn percentile(sorted: &[f32], p: f32) -> f32 {
    if sorted.is_empty() {
        return 0.0;
    }
    let idx = ((sorted.len() - 1) as f32 * p).round() as usize;
    sorted[idx.min(sorted.len() - 1)]
}

/// Writes the captured utterance to ~/.rigel/debug so the actual audio the
/// pipeline saw can be inspected offline. Best-effort; never fails the flow.
fn dump_debug_wav(samples: &[f32], sample_rate: u32, channels: u16, tag: &str) -> Option<PathBuf> {
    let home = std::env::var_os("HOME").map(PathBuf::from)?;
    let dir = home.join(".rigel").join("debug");
    std::fs::create_dir_all(&dir).ok()?;
    let stamp = SystemTime::now().duration_since(UNIX_EPOCH).ok()?.as_millis();
    let path = dir.join(format!("utt_{stamp}_{tag}.wav"));
    let spec = hound::WavSpec {
        channels,
        sample_rate,
        bits_per_sample: 32,
        sample_format: hound::SampleFormat::Float,
    };
    let mut writer = hound::WavWriter::create(&path, spec).ok()?;
    for &s in samples {
        writer.write_sample(s).ok()?;
    }
    writer.finalize().ok()?;

    // Prune old dumps.
    if let Ok(entries) = std::fs::read_dir(&dir) {
        let mut files: Vec<PathBuf> = entries
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|p| p.extension().map(|x| x == "wav").unwrap_or(false))
            .collect();
        files.sort();
        while files.len() > DEBUG_KEEP {
            let _ = std::fs::remove_file(files.remove(0));
        }
    }
    Some(path)
}

fn describe_detection(d: &RustpotterDetection) -> String {
    let mut per_ref: Vec<(String, f32)> = d.scores.iter().map(|(k, v)| (k.clone(), *v)).collect();
    per_ref.sort_by(|a, b| a.0.cmp(&b.0));
    format!(
        "score={:.3} avg_score={:.3} counter={} gain={:.2} per_ref={:?}",
        d.score, d.avg_score, d.counter, d.gain, per_ref
    )
}

/// Starts the background listening thread. Returns immediately — errors
/// discovered inside the thread (mic disappears, etc.) surface as
/// `voice://error` events rather than a return value.
pub fn start(app: AppHandle) -> Result<ListenerHandle, String> {
    let wakeword_path = enroll::wakeword_model_path()?;
    if !wakeword_path.exists() {
        return Err("No wake word trained yet. Set it up in Settings → Voice.".to_string());
    }
    if !stt::model_downloaded() {
        return Err("Speech-to-text model not downloaded yet. Set it up in Settings → Voice.".to_string());
    }

    let stop_flag = Arc::new(AtomicBool::new(false));
    let stop_flag_thread = stop_flag.clone();

    std::thread::spawn(move || {
        if let Err(e) = run(app.clone(), wakeword_path, stop_flag_thread) {
            let _ = app.emit("voice://error", serde_json::json!({ "message": e }));
        }
    });

    Ok(ListenerHandle { stop_flag })
}

fn run(app: AppHandle, wakeword_path: PathBuf, stop_flag: Arc<AtomicBool>) -> Result<(), String> {
    let host = cpal::default_host();
    let device = host
        .default_input_device()
        .ok_or_else(|| "No microphone found.".to_string())?;
    let supported = device
        .default_input_config()
        .map_err(|e| format!("Failed to read microphone config: {e}"))?;
    if supported.sample_format() != cpal::SampleFormat::F32 {
        return Err(format!(
            "Unsupported microphone sample format {:?} (expected f32).",
            supported.sample_format()
        ));
    }
    let sample_rate = supported.sample_rate();
    let channels = supported.channels();
    let stream_config: cpal::StreamConfig = supported.into();

    let mut rp_config = RustpotterConfig::default();
    rp_config.fmt.sample_rate = sample_rate as usize;
    rp_config.fmt.channels = channels;
    // Detector thresholds stay at the library defaults (0.5 / 0.2). With
    // vad_mode = None (the default) rustpotter scores *every* frame, silence
    // included, against the reference — its own adaptive voice-activity gate
    // stops near-silent frames from ever reaching the matcher.
    rp_config.detector.vad_mode = Some(rustpotter::VADMode::Easy);
    let mut rustpotter =
        Rustpotter::new(&rp_config).map_err(|e| format!("Failed to start wake-word detector: {e}"))?;
    rustpotter
        .add_wakeword_from_file("rigel", &wakeword_path.to_string_lossy())
        .map_err(|e| format!("Failed to load wake word: {e}"))?;
    // process_samples silently no-ops (returns None, no error) unless the
    // slice it's given is exactly this length — cpal's callback buffers are
    // whatever size the OS/driver chooses, essentially never a match, so we
    // re-chunk into a dedicated fixed-size frame buffer below.
    let samples_per_frame = rustpotter.get_samples_per_frame();
    log::info!(
        "voice listener: mic {}Hz/{}ch, wake-word frame = {} samples, detector threshold={:.2} avg_threshold={:.2} min_scores={} eager={} vad={} gain_norm={} band_pass={}",
        sample_rate,
        channels,
        samples_per_frame,
        rp_config.detector.threshold,
        rp_config.detector.avg_threshold,
        rp_config.detector.min_scores,
        rp_config.detector.eager,
        rp_config.detector.vad_mode.is_some(),
        rp_config.filters.gain_normalizer.enabled,
        rp_config.filters.band_pass.enabled,
    );
    let mut frame_buffer: Vec<f32> = Vec::with_capacity(samples_per_frame * 2);

    let (tx, rx) = mpsc::channel::<Vec<f32>>();
    let stream = device
        .build_input_stream(
            &stream_config,
            move |data: &[f32], _: &cpal::InputCallbackInfo| {
                let _ = tx.send(data.to_vec());
            },
            |err| log::error!("microphone input error: {err}"),
            None,
        )
        .map_err(|e| format!("Failed to open microphone: {e}"))?;
    stream
        .play()
        .map_err(|e| format!("Failed to start microphone: {e}"))?;

    let _ = app.emit("voice://state", serde_json::json!({ "state": "idle" }));

    let mut mode = Mode::Listening;
    let mut last_status = Instant::now();
    let mut noise_floor: f32 = 0.0;
    let mut gated_last_chunk = false;
    loop {
        if stop_flag.load(Ordering::SeqCst) {
            break;
        }
        let chunk = match rx.recv_timeout(Duration::from_millis(200)) {
            Ok(c) => c,
            Err(RecvTimeoutError::Timeout) => continue,
            Err(RecvTimeoutError::Disconnected) => break,
        };

        match &mut mode {
            Mode::Listening => {
                let level = rms(&chunk);

                // Deaf while Rigel itself is talking (and briefly after):
                // the mic hears the speakers, and the detector must not be
                // fed our own TTS output.
                if super::tts_blocks_listening() {
                    if !gated_last_chunk {
                        log::info!("voice listener: muted while speaking");
                        gated_last_chunk = true;
                    }
                    frame_buffer.clear();
                    continue;
                }
                if gated_last_chunk {
                    gated_last_chunk = false;
                    rustpotter.reset();
                    frame_buffer.clear();
                    log::info!("voice listener: unmuted, detector reset");
                    continue;
                }

                // Slow-moving estimate of the idle room level; only updated
                // from chunks that look like background (not sudden spikes).
                // cpal can deliver all-zero chunks right after the stream
                // opens; seeding the floor with one of those would pin it at
                // 0 forever (nothing is ever < 0 * 3), so wait for real audio.
                if noise_floor == 0.0 {
                    if level > 0.0 {
                        noise_floor = level;
                    }
                } else if level < noise_floor * 3.0 {
                    noise_floor += NOISE_FLOOR_ALPHA * (level - noise_floor);
                }
                if last_status.elapsed() >= STATUS_EVERY {
                    last_status = Instant::now();
                    log::info!(
                        "voice listener: still listening, mic rms={:.5} noise_floor={:.5} speech_threshold={:.5}",
                        level,
                        noise_floor,
                        SPEECH_RMS_FLOOR.max(SPEECH_OVER_NOISE * noise_floor)
                    );
                }

                frame_buffer.extend_from_slice(&chunk);
                let mut detected: Option<RustpotterDetection> = None;
                while frame_buffer.len() >= samples_per_frame {
                    let frame: Vec<f32> = frame_buffer.drain(0..samples_per_frame).collect();
                    if let Some(d) = rustpotter.process_samples(frame) {
                        detected = Some(d);
                        break;
                    }
                }
                if let Some(d) = detected {
                    let speech_threshold = SPEECH_RMS_FLOOR.max(SPEECH_OVER_NOISE * noise_floor);
                    log::info!(
                        "voice listener: wake word detected — {} | trigger chunk rms={:.5} noise_floor={:.5} speech_threshold={:.5}",
                        describe_detection(&d),
                        level,
                        noise_floor,
                        speech_threshold
                    );
                    let _ = app.emit("voice://state", serde_json::json!({ "state": "recording" }));
                    // Whatever is still in frame_buffer is audio *after* the
                    // frame that completed the wake word — that's the start of
                    // the command, so it seeds the recording. The frames
                    // already drained (the wake word itself) are not included,
                    // so whisper doesn't transcribe "Rigel" along with it.
                    let mut buffer = std::mem::take(&mut frame_buffer);
                    buffer.reserve(sample_rate as usize * channels as usize * 6);
                    mode = Mode::Recording {
                        buffer,
                        last_voice: Instant::now(),
                        started: Instant::now(),
                        heard_speech: false,
                        speech_threshold,
                        chunk_levels: Vec::with_capacity(512),
                    };
                }
            }
            Mode::Recording {
                buffer,
                last_voice,
                started,
                heard_speech,
                speech_threshold,
                chunk_levels,
            } => {
                let level = rms(&chunk);
                chunk_levels.push(level);
                if level > *speech_threshold {
                    *last_voice = Instant::now();
                    *heard_speech = true;
                }
                buffer.extend_from_slice(&chunk);

                // Before any speech is heard, only the onset grace period and
                // the hard cap can end recording — a quiet pause right after
                // the wake word must not cut the command off before it starts.
                let went_quiet = *heard_speech && last_voice.elapsed() >= SILENCE_HANGOVER;
                let gave_up_waiting = !*heard_speech && started.elapsed() >= SPEECH_ONSET_GRACE;
                let timed_out = started.elapsed() >= MAX_RECORDING;

                if went_quiet || gave_up_waiting || timed_out {
                    let recorded = std::mem::take(buffer);
                    let mut levels = std::mem::take(chunk_levels);
                    levels.sort_by(|a, b| a.total_cmp(b));
                    let reason = if timed_out {
                        "timed out"
                    } else if went_quiet {
                        "went quiet"
                    } else {
                        "gave up waiting for speech"
                    };
                    let had_speech = *heard_speech;
                    let dump = dump_debug_wav(
                        &recorded,
                        sample_rate,
                        channels,
                        if had_speech { "speech" } else { "nospeech" },
                    );
                    log::info!(
                        "voice listener: recording ended ({reason}), {:.2}s captured, rms={:.5} peak_chunk={:.5} p95_chunk={:.5} median_chunk={:.5} speech_threshold={:.5} heard_speech={} dump={:?}",
                        recorded.len() as f32 / sample_rate as f32 / channels as f32,
                        rms(&recorded),
                        percentile(&levels, 1.0),
                        percentile(&levels, 0.95),
                        percentile(&levels, 0.5),
                        speech_threshold,
                        had_speech,
                        dump
                    );
                    mode = Mode::Listening;
                    rustpotter.reset();

                    // Drop any audio queued while we were recording so the
                    // detector doesn't wake back up on stale samples.
                    while rx.try_recv().is_ok() {}

                    if !had_speech {
                        // Nothing above the speech threshold was ever heard —
                        // this was a false trigger (or the user said nothing).
                        // Don't ask whisper to hallucinate over silence.
                        let _ = app.emit("voice://state", serde_json::json!({ "state": "idle" }));
                        continue;
                    }

                    let _ = app.emit("voice://state", serde_json::json!({ "state": "thinking" }));
                    let app_for_stt = app.clone();
                    let stop_for_stt = stop_flag.clone();
                    std::thread::spawn(move || match stt::transcribe(&recorded, sample_rate, channels) {
                        // Voice was switched off while whisper was running —
                        // don't revive an interaction the user just ended.
                        Ok(_) if stop_for_stt.load(Ordering::SeqCst) => {}
                        Ok(text) if !text.is_empty() => {
                            log::info!("voice listener: transcript = {text:?}");
                            let _ = app_for_stt.emit("voice://transcript", serde_json::json!({ "text": text }));
                        }
                        Ok(_) => {
                            log::info!("voice listener: transcript empty / non-speech, dropped");
                            let _ = app_for_stt.emit("voice://state", serde_json::json!({ "state": "idle" }));
                        }
                        Err(e) => {
                            log::error!("voice listener: transcription failed: {e}");
                            let _ = app_for_stt.emit("voice://error", serde_json::json!({ "message": e }));
                            // Without this the orb stays on "Working…" forever
                            // even though the mic is already listening again.
                            let _ = app_for_stt.emit("voice://state", serde_json::json!({ "state": "idle" }));
                        }
                    });
                }
            }
        }
    }

    drop(stream);
    Ok(())
}
