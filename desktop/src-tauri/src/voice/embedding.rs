//! Speaker embeddings: fbank features -> Wespeaker ECAPA-TDNN (ONNX) -> 192 numbers.
//!
//! The model file is checked against MODEL_SHA256 before ONNX Runtime opens it.
//! Compile-verified on the Mac only once `cargo build` is run there; see the
//! reference test for the numerical check against tools/speaker_ref_check.py.

use std::path::Path;

use ort::{session::Session, value::Tensor};

use super::fbank::{fbank, frame_count, NUM_MEL_BINS};
use super::model::{verify_file, MODEL_SHA256};

pub const EMBEDDING_DIM: usize = 192;

fn err<E: std::fmt::Display>(e: E) -> String {
    e.to_string()
}

pub struct SpeakerEncoder {
    session: Session,
    input_name: String,
}

impl SpeakerEncoder {
    /// Verifies the model's checksum, then opens it with ONNX Runtime.
    pub fn load(path: &Path) -> Result<Self, String> {
        verify_file(path, MODEL_SHA256)?;
        let session = Session::builder()
            .map_err(err)?
            .commit_from_file(path)
            .map_err(err)?;
        let input_name = session
            .inputs()
            .first()
            .ok_or("speaker model has no inputs")?
            .name()
            .to_string();
        Ok(Self { session, input_name })
    }

    /// Embedding for 16 kHz mono samples in [-1, 1]. Needs at least 25 ms of audio.
    pub fn embed(&mut self, samples: &[f32]) -> Result<Vec<f32>, String> {
        let frames = frame_count(samples.len());
        if frames == 0 {
            return Err("clip too short for a speaker embedding".into());
        }
        let feats = fbank(samples);
        let input = Tensor::from_array(([1usize, frames, NUM_MEL_BINS], feats)).map_err(err)?;
        let outputs = self
            .session
            .run(ort::inputs![self.input_name.as_str() => input])
            .map_err(err)?;
        let (_shape, data) = outputs[0].try_extract_tensor::<f32>().map_err(err)?;
        if data.len() != EMBEDDING_DIM {
            return Err(format!("expected {EMBEDDING_DIM} numbers, model gave {}", data.len()));
        }
        Ok(data.to_vec())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn missing_model_is_an_error() {
        assert!(SpeakerEncoder::load(Path::new("/nonexistent/model.onnx")).is_err());
    }

    #[test]
    #[ignore = "needs RIGEL_MODEL_PATH, RIGEL_REF_WAV and RIGEL_REF_EMBEDDING; see tools/speaker_ref_check.py"]
    fn matches_reference_embedding() {
        let model = std::env::var("RIGEL_MODEL_PATH").expect("set RIGEL_MODEL_PATH");
        let wav = std::env::var("RIGEL_REF_WAV").expect("set RIGEL_REF_WAV");
        let ref_path = std::env::var("RIGEL_REF_EMBEDDING").expect("set RIGEL_REF_EMBEDDING");

        let mut reader = hound::WavReader::open(&wav).expect("open wav");
        let samples: Vec<f32> = reader
            .samples::<i16>()
            .map(|s| s.expect("read sample") as f32 / 32768.0)
            .collect();

        let mut encoder = SpeakerEncoder::load(Path::new(&model)).expect("load model");
        let ours = encoder.embed(&samples).expect("embed");
        let text = std::fs::read_to_string(&ref_path).expect("read reference");
        let theirs: Vec<f32> = text
            .split_ascii_whitespace()
            .map(|t| t.parse().expect("parse reference value"))
            .collect();

        assert_eq!(ours.len(), theirs.len());
        let max_diff = ours
            .iter()
            .zip(&theirs)
            .map(|(a, b)| (a - b).abs())
            .fold(0.0_f32, f32::max);
        eprintln!("embedding dims={} max abs diff={max_diff}", ours.len());
        assert!(max_diff < 1e-3, "max abs diff {max_diff} is too large");
    }
}
