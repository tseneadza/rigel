//! Microphone capture. Rigel targets macOS only, where cpal's default input
//! device reliably reports an f32 stream, so that's the only sample format
//! handled here — anything else surfaces as a clear error instead of being
//! silently downmixed/converted.

use std::sync::{Arc, Mutex};
use std::time::Duration;

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};

pub struct CapturedAudio {
    pub samples: Vec<f32>,
    pub sample_rate: u32,
    pub channels: u16,
}

/// Records `seconds` of audio from the default input device, blocking the
/// calling thread for the duration. Used for short, on-demand recordings
/// (wake-word enrollment samples) — not for continuous listening, which
/// needs a long-lived stream instead.
pub fn record_seconds(seconds: f32) -> Result<CapturedAudio, String> {
    let host = cpal::default_host();
    let device = host.default_input_device().ok_or_else(|| {
        "No microphone found. Check System Settings → Privacy & Security → Microphone."
            .to_string()
    })?;
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

    let buffer: Arc<Mutex<Vec<f32>>> = Arc::new(Mutex::new(Vec::new()));
    let buffer_cb = buffer.clone();

    let stream = device
        .build_input_stream(
            &stream_config,
            move |data: &[f32], _: &cpal::InputCallbackInfo| {
                if let Ok(mut buf) = buffer_cb.lock() {
                    buf.extend_from_slice(data);
                }
            },
            |err| log::error!("microphone input error: {err}"),
            None,
        )
        .map_err(|e| format!("Failed to open microphone: {e}"))?;

    stream
        .play()
        .map_err(|e| format!("Failed to start microphone: {e}"))?;
    std::thread::sleep(Duration::from_secs_f32(seconds));
    drop(stream);

    let samples = Arc::try_unwrap(buffer)
        .map(|m| m.into_inner().unwrap_or_default())
        .unwrap_or_else(|arc| arc.lock().map(|g| g.clone()).unwrap_or_default());

    Ok(CapturedAudio {
        samples,
        sample_rate,
        channels,
    })
}
