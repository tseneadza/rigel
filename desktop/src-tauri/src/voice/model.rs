//! Verifies the speaker-embedding model file before ONNX Runtime loads it.
//!
//! Model: Wespeaker `voxceleb_ECAPA512_LM.onnx`, repo
//! `Wespeaker/wespeaker-ecapa-tdnn512-LM`, licence CC-BY-4.0 (attribution
//! required; see MODEL_ATTRIBUTION). The hash below is taken from the
//! Hugging Face file listing and must be confirmed with `shasum -a 256` on
//! the file Tony downloads before this check is trusted.

use std::fs;
use std::path::Path;

use sha2::{Digest, Sha256};

pub const MODEL_FILE_NAME: &str = "voxceleb_ECAPA512_LM.onnx";
pub const MODEL_SHA256: &str = "d71b85d9b48058ef68004f04f1b78acebefb9dfcf542e19b976a12a5ad1f10b0";
pub const MODEL_ATTRIBUTION: &str = "Speaker model: Wespeaker ECAPA-TDNN (voxceleb_ECAPA512_LM), CC-BY-4.0, https://huggingface.co/Wespeaker/wespeaker-ecapa-tdnn512-LM";

/// Lowercase hex SHA-256 of `bytes`.
pub fn sha256_hex(bytes: &[u8]) -> String {
    Sha256::digest(bytes).iter().map(|b| format!("{b:02x}")).collect()
}

/// True when `bytes` hash to `expected_hex` (case-insensitive).
pub fn verify_bytes(bytes: &[u8], expected_hex: &str) -> bool {
    sha256_hex(bytes).eq_ignore_ascii_case(expected_hex)
}

/// Reads the file at `path` and checks it against `expected_hex`.
pub fn verify_file(path: &Path, expected_hex: &str) -> Result<(), String> {
    let bytes = fs::read(path).map_err(|e| format!("cannot read model {}: {e}", path.display()))?;
    if verify_bytes(&bytes, expected_hex) {
        Ok(())
    } else {
        Err(format!("model checksum mismatch for {}", path.display()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sha256_matches_known_vectors() {
        assert_eq!(sha256_hex(b""), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
        assert_eq!(sha256_hex(b"abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    }

    #[test]
    fn verify_bytes_accepts_match_in_any_case_and_rejects_others() {
        let h = sha256_hex(b"abc");
        assert!(verify_bytes(b"abc", &h));
        assert!(verify_bytes(b"abc", &h.to_uppercase()));
        assert!(!verify_bytes(b"abd", &h));
    }

    #[test]
    fn pinned_hash_is_well_formed() {
        assert_eq!(MODEL_SHA256.len(), 64);
        assert!(MODEL_SHA256.chars().all(|c| c.is_ascii_hexdigit()));
    }

    #[test]
    fn verify_file_reports_mismatch_for_a_wrong_file() {
        let path = std::env::temp_dir().join("rigel-model-check-test.bin");
        fs::write(&path, b"not the model").unwrap();
        assert!(verify_file(&path, MODEL_SHA256).is_err());
        assert!(verify_file(&path, &sha256_hex(b"not the model")).is_ok());
        let _ = fs::remove_file(&path);
    }
}
