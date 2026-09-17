//! Wake-word enrollment: record the user saying their wake phrase a few
//! times and build a rustpotter "wakeword reference" from the samples.
//!
//! There's no pretrained "Hey Rigel" model to ship — rustpotter's reference
//! mode (as opposed to its trained-neural-net mode) works from 3-8 short
//! recordings of a phrase, comparing live audio against them via dynamic
//! time warping. That's a deliberate fit here: it needs no vendor account,
//! no network call, and no training data beyond what the user provides in
//! this flow.

use std::path::PathBuf;
use std::time::Duration;

use rustpotter::{WakewordRef, WakewordRefBuildFromFiles, WakewordSave};
use tauri::{AppHandle, Emitter};

use super::capture;

const SAMPLES_NEEDED: usize = 3;
// Longer than a single short word needs, but a comfortable margin for
// multi-word phrases ("Hey Rigel") and for reacting to the "recording"
// prompt without clipping the start of the phrase.
const SAMPLE_SECONDS: f32 = 2.5;
const PRE_ROLL: Duration = Duration::from_millis(1500);
/// MFCC coefficient count — matches rustpotter-cli's own default, which is
/// a well-exercised value for short spoken-phrase comparison.
const MFCC_SIZE: u16 = 16;

fn rigel_dir() -> Result<PathBuf, String> {
    let home = std::env::var_os("HOME")
        .map(PathBuf::from)
        .ok_or("HOME environment variable not set")?;
    let dir = home.join(".rigel");
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    Ok(dir)
}

pub fn wakeword_model_path() -> Result<PathBuf, String> {
    Ok(rigel_dir()?.join("wakeword.rpw"))
}

fn write_wav(
    path: &std::path::Path,
    samples: &[f32],
    sample_rate: u32,
    channels: u16,
) -> Result<(), String> {
    let spec = hound::WavSpec {
        channels,
        sample_rate,
        bits_per_sample: 32,
        sample_format: hound::SampleFormat::Float,
    };
    let mut writer = hound::WavWriter::create(path, spec).map_err(|e| e.to_string())?;
    for &sample in samples {
        writer.write_sample(sample).map_err(|e| e.to_string())?;
    }
    writer.finalize().map_err(|e| e.to_string())
}

/// Analysis window for the trim, and how much silence to keep around the
/// detected speech so the word's onset/offset aren't clipped.
const TRIM_WINDOW_MS: usize = 20;
const TRIM_PAD_MS: usize = 150;
/// A window counts as speech if it is louder than all of: an absolute floor,
/// a multiple of the recording's quietest level, and a fraction of its
/// loudest level. The last one is what keeps a mouse click or a breath in the
/// reaction-time silence from opening the speech window early on a mic with
/// a noisy floor.
const TRIM_OVER_FLOOR: f32 = 4.0;
const TRIM_ABS_FLOOR: f32 = 0.002;
const TRIM_PEAK_FRACTION: f32 = 0.12;
/// Speech windows may be separated by gaps up to this long (a stop consonant,
/// the pause between "Hey" and "Rigel") and still count as one utterance.
const TRIM_MAX_GAP_MS: usize = 200;
/// Anything shorter than this after trimming can't have been a spoken word.
const MIN_SPEECH_MS: usize = 150;

pub struct Trimmed {
    pub samples: Vec<f32>,
    pub speech_ms: usize,
    pub peak_rms: f32,
    pub floor_rms: f32,
}

/// Cuts a raw enrollment recording down to just the spoken phrase (plus a
/// little padding). rustpotter builds its reference from the *whole* file
/// and does no endpointing of its own, so an untrimmed 2.5 s sample that is
/// ~80 % silence gives a matcher that mostly recognises silence — it then
/// trips on background noise and misses the actual word.
///
/// Returns `None` if no speech-like energy was found.
pub fn trim_to_speech(samples: &[f32], sample_rate: u32, channels: u16) -> Option<Trimmed> {
    let frame = channels.max(1) as usize;
    let win = (sample_rate as usize * TRIM_WINDOW_MS / 1000) * frame;
    if win == 0 || samples.len() < win * 2 {
        return None;
    }
    let levels: Vec<f32> = samples
        .chunks(win)
        .map(|c| (c.iter().map(|s| s * s).sum::<f32>() / c.len() as f32).sqrt())
        .collect();
    let mut sorted = levels.clone();
    sorted.sort_by(|a, b| a.total_cmp(b));
    // Floor = 10th percentile, so a single dead window doesn't define it.
    let floor = sorted[(sorted.len() - 1) / 10];
    let peak = *sorted.last().unwrap_or(&0.0);
    let threshold = TRIM_ABS_FLOOR.max(floor * TRIM_OVER_FLOOR);

    let threshold = threshold.max(peak * TRIM_PEAK_FRACTION);

    // Anchor on the loudest window and grow outward while the signal stays
    // above threshold, tolerating short gaps — so the trim lands on the word
    // itself rather than on the first stray noise that clears the threshold.
    let anchor = levels
        .iter()
        .enumerate()
        .max_by(|a, b| a.1.total_cmp(b.1))
        .map(|(i, _)| i)?;
    if levels[anchor] <= threshold {
        return None;
    }
    let max_gap = TRIM_MAX_GAP_MS / TRIM_WINDOW_MS;
    let mut first = anchor;
    let mut gap = 0;
    for i in (0..anchor).rev() {
        if levels[i] > threshold {
            first = i;
            gap = 0;
        } else {
            gap += 1;
            if gap > max_gap {
                break;
            }
        }
    }
    let mut last = anchor;
    gap = 0;
    for i in anchor + 1..levels.len() {
        if levels[i] > threshold {
            last = i;
            gap = 0;
        } else {
            gap += 1;
            if gap > max_gap {
                break;
            }
        }
    }
    let speech_ms = (last - first + 1) * TRIM_WINDOW_MS;
    if speech_ms < MIN_SPEECH_MS {
        return None;
    }

    let pad = TRIM_PAD_MS / TRIM_WINDOW_MS;
    let start = first.saturating_sub(pad) * win;
    let end = ((last + 1 + pad) * win).min(samples.len());
    Some(Trimmed {
        samples: samples[start..end].to_vec(),
        speech_ms,
        peak_rms: peak,
        floor_rms: floor,
    })
}

/// Records `SAMPLES_NEEDED` utterances and builds+saves the wakeword
/// reference. Emits `voice://enroll-progress` before each recording so the
/// UI can prompt "say it now" with correct timing. Blocking — Tauri runs
/// sync commands off the UI thread automatically.
fn enroll(app: &AppHandle) -> Result<PathBuf, String> {
    let tmp_dir = rigel_dir()?.join("enroll_tmp");
    std::fs::create_dir_all(&tmp_dir).map_err(|e| e.to_string())?;

    let cleanup = |tmp_dir: &PathBuf| {
        let _ = std::fs::remove_dir_all(tmp_dir);
    };

    let mut sample_paths = Vec::with_capacity(SAMPLES_NEEDED);
    for i in 0..SAMPLES_NEEDED {
        let _ = app.emit(
            "voice://enroll-progress",
            serde_json::json!({ "stage": "ready", "index": i, "total": SAMPLES_NEEDED }),
        );
        std::thread::sleep(PRE_ROLL);
        let _ = app.emit(
            "voice://enroll-progress",
            serde_json::json!({ "stage": "recording", "index": i, "total": SAMPLES_NEEDED }),
        );

        let audio = match capture::record_seconds(SAMPLE_SECONDS) {
            Ok(a) => a,
            Err(e) => {
                cleanup(&tmp_dir);
                return Err(e);
            }
        };
        let trimmed = match trim_to_speech(&audio.samples, audio.sample_rate, audio.channels) {
            Some(t) => t,
            None => {
                cleanup(&tmp_dir);
                log::warn!(
                    "enroll: sample {} had no detectable speech (overall rms={:.5})",
                    i + 1,
                    (audio.samples.iter().map(|s| s * s).sum::<f32>() / audio.samples.len().max(1) as f32).sqrt()
                );
                return Err(format!(
                    "Didn't hear anything on recording {} of {SAMPLES_NEEDED}. Speak clearly at normal volume when the prompt appears, then try again.",
                    i + 1
                ));
            }
        };
        log::info!(
            "enroll: sample {} trimmed {:.2}s -> {:.2}s (speech {}ms, peak rms={:.4}, floor rms={:.5})",
            i + 1,
            audio.samples.len() as f32 / audio.sample_rate as f32 / audio.channels.max(1) as f32,
            trimmed.samples.len() as f32 / audio.sample_rate as f32 / audio.channels.max(1) as f32,
            trimmed.speech_ms,
            trimmed.peak_rms,
            trimmed.floor_rms
        );
        let path = tmp_dir.join(format!("sample_{i}.wav"));
        if let Err(e) = write_wav(&path, &trimmed.samples, audio.sample_rate, audio.channels) {
            cleanup(&tmp_dir);
            return Err(e);
        }
        // Keep inspectable copies (raw + trimmed) — the tmp dir is deleted
        // once the reference is built, and enrollment quality is the thing
        // most worth checking when detection misbehaves.
        if let Ok(debug_dir) = rigel_dir().map(|d| d.join("debug")) {
            if std::fs::create_dir_all(&debug_dir).is_ok() {
                let _ = write_wav(
                    &debug_dir.join(format!("enroll_{i}_raw.wav")),
                    &audio.samples,
                    audio.sample_rate,
                    audio.channels,
                );
                let _ = write_wav(
                    &debug_dir.join(format!("enroll_{i}_trimmed.wav")),
                    &trimmed.samples,
                    audio.sample_rate,
                    audio.channels,
                );
            }
        }
        sample_paths.push(path.to_string_lossy().to_string());
    }

    let wakeword = WakewordRef::new_from_sample_files(
        "rigel".to_string(),
        None,
        None,
        sample_paths,
        MFCC_SIZE,
    );
    cleanup(&tmp_dir);
    let wakeword = wakeword?;

    let model_path = wakeword_model_path()?;
    wakeword
        .save_to_file(&model_path.to_string_lossy())
        .map_err(|e| e.to_string())?;
    Ok(model_path)
}

#[tauri::command]
pub fn voice_enroll_wakeword(app: AppHandle) -> Result<(), String> {
    let result = enroll(&app);
    let _ = app.emit(
        "voice://enroll-done",
        serde_json::json!({ "ok": result.is_ok(), "error": result.as_ref().err() }),
    );
    result.map(|_| ())
}

#[tauri::command]
pub fn voice_wakeword_status() -> Result<bool, String> {
    Ok(wakeword_model_path()?.exists())
}

#[cfg(test)]
mod tests {
    use super::trim_to_speech;

    fn synth(sample_rate: u32, quiet_ms: usize, loud_ms: usize, trailing_ms: usize) -> Vec<f32> {
        let per_ms = sample_rate as usize / 1000;
        let mut v = Vec::new();
        // Room noise at ~0.0003 rms, like the user's mic.
        let noise = |i: usize| (i as f32 * 0.37).sin() * 0.0004;
        for i in 0..quiet_ms * per_ms {
            v.push(noise(i));
        }
        // A "word": 200 Hz tone at ~0.05 rms.
        for i in 0..loud_ms * per_ms {
            v.push((i as f32 / sample_rate as f32 * 200.0 * std::f32::consts::TAU).sin() * 0.07);
        }
        for i in 0..trailing_ms * per_ms {
            v.push(noise(i));
        }
        v
    }

    #[test]
    fn trims_untrimmed_enrollment_sample_to_the_word() {
        let sr = 16000;
        let raw = synth(sr, 1000, 500, 1000);
        let t = trim_to_speech(&raw, sr, 1).expect("speech should be found");
        let secs = t.samples.len() as f32 / sr as f32;
        // 0.5 s of word + up to 0.15 s pad each side.
        assert!(secs > 0.5 && secs < 0.9, "trimmed length {secs}s");
        assert!(t.speech_ms >= 480 && t.speech_ms <= 540, "speech_ms {}", t.speech_ms);
        assert!(t.peak_rms > 0.04);
        assert!(t.floor_rms < 0.001);
    }

    #[test]
    fn ignores_a_click_in_the_leading_silence() {
        let sr = 16000;
        let per_ms = sr as usize / 1000;
        let mut raw = synth(sr, 300, 0, 0);
        // A short click (30 ms at 0.01 rms — above 4x floor, well under the word).
        for i in 0..30 * per_ms {
            raw.push((i as f32 * 0.9).sin() * 0.014);
        }
        raw.extend(synth(sr, 1000, 500, 1000));
        let t = trim_to_speech(&raw, sr, 1).expect("speech should be found");
        let secs = t.samples.len() as f32 / sr as f32;
        assert!(secs < 0.9, "click should not extend the trim: {secs}s");
        assert!(t.speech_ms >= 480 && t.speech_ms <= 540, "speech_ms {}", t.speech_ms);
    }

    #[test]
    fn rejects_silence_only_sample() {
        let sr = 16000;
        let raw = synth(sr, 2500, 0, 0);
        assert!(trim_to_speech(&raw, sr, 1).is_none());
    }

    #[test]
    fn rejects_click_shorter_than_a_word() {
        let sr = 16000;
        let raw = synth(sr, 1000, 60, 1000);
        assert!(trim_to_speech(&raw, sr, 1).is_none());
    }
}

#[tauri::command]
pub fn voice_clear_wakeword() -> Result<(), String> {
    let path = wakeword_model_path()?;
    if path.exists() {
        std::fs::remove_file(&path).map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[cfg(test)]
mod real_audio {
    /// Runs the trim over whatever raw enrollment recordings are on this
    /// machine (~/.rigel/debug/enroll_*_raw.wav). Ignored by default because
    /// it depends on local files; run with `--ignored --nocapture`.
    #[test]
    #[ignore]
    fn trim_real_enrollment_recordings() {
        let home = std::env::var("HOME").unwrap();
        for i in 0..8 {
            let path = format!("{home}/.rigel/debug/enroll_{i}_raw.wav");
            let Ok(mut reader) = hound::WavReader::open(&path) else { continue };
            let spec = reader.spec();
            let samples: Vec<f32> = reader.samples::<f32>().map(|s| s.unwrap()).collect();
            let secs = |n: usize| n as f32 / spec.sample_rate as f32 / spec.channels as f32;
            match super::trim_to_speech(&samples, spec.sample_rate, spec.channels) {
                Some(t) => println!(
                    "{path}: {:.2}s -> {:.2}s (speech {}ms, peak {:.3}, floor {:.4})",
                    secs(samples.len()),
                    secs(t.samples.len()),
                    t.speech_ms,
                    t.peak_rms,
                    t.floor_rms
                ),
                None => println!("{path}: NO SPEECH FOUND"),
            }
        }
    }
}
