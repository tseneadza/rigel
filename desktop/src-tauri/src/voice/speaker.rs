//! Speaker matching: decides whether an utterance was spoken by the enrolled
//! user. This module only compares embedding vectors. The embedder (an
//! ECAPA-TDNN model run through ONNX Runtime) produces the vectors and comes
//! in a later step.

/// Placeholder threshold. Not tuned yet: it is set from measurements on
/// Tony's own recorded clips (including TV audio) before it becomes a default.
pub const DEFAULT_THRESHOLD: f32 = 0.5;

/// Cosine similarity in [-1, 1]. Returns 0.0 when either vector is empty,
/// all zeros, or the two lengths differ, so bad input never counts as a match.
pub fn cosine(a: &[f32], b: &[f32]) -> f32 {
    if a.is_empty() || a.len() != b.len() {
        return 0.0;
    }
    let (mut dot, mut norm_a, mut norm_b) = (0.0f32, 0.0f32, 0.0f32);
    for (x, y) in a.iter().zip(b.iter()) {
        dot += x * y;
        norm_a += x * x;
        norm_b += y * y;
    }
    if norm_a == 0.0 || norm_b == 0.0 {
        return 0.0;
    }
    dot / (norm_a.sqrt() * norm_b.sqrt())
}

/// Best similarity between the utterance and any enrolled vector. With no
/// enrolled vectors this is negative infinity, so nothing matches.
pub fn best_score(utterance: &[f32], enrolled: &[Vec<f32>]) -> f32 {
    enrolled
        .iter()
        .map(|e| cosine(utterance, e))
        .fold(f32::NEG_INFINITY, f32::max)
}

/// True when the utterance matches the enrolled voice at or above `threshold`.
/// No enrolled vectors means no match: the check fails closed.
pub fn is_enrolled_voice(utterance: &[f32], enrolled: &[Vec<f32>], threshold: f32) -> bool {
    !enrolled.is_empty() && best_score(utterance, enrolled) >= threshold
}

#[cfg(test)]
mod tests {
    use super::*;

    fn close(a: f32, b: f32) -> bool {
        (a - b).abs() < 1e-5
    }

    #[test]
    fn cosine_of_known_pairs() {
        assert!(close(cosine(&[1.0, 2.0], &[1.0, 2.0]), 1.0));
        assert!(close(cosine(&[1.0, 0.0], &[0.0, 1.0]), 0.0));
        assert!(close(cosine(&[1.0, 0.0], &[-1.0, 0.0]), -1.0));
    }

    #[test]
    fn cosine_rejects_bad_input() {
        assert_eq!(cosine(&[], &[]), 0.0);
        assert_eq!(cosine(&[0.0, 0.0], &[1.0, 1.0]), 0.0);
        assert_eq!(cosine(&[1.0, 2.0], &[1.0, 2.0, 3.0]), 0.0);
    }

    #[test]
    fn same_voice_matches_and_other_voice_does_not() {
        let enrolled = vec![vec![1.0, 0.1, 0.0]];
        assert!(is_enrolled_voice(&[0.9, 0.12, 0.0], &enrolled, DEFAULT_THRESHOLD));
        assert!(!is_enrolled_voice(&[0.0, 0.0, 1.0], &enrolled, DEFAULT_THRESHOLD));
    }

    #[test]
    fn no_enrolled_voice_never_matches() {
        assert!(!is_enrolled_voice(&[1.0, 0.0], &[], DEFAULT_THRESHOLD));
        assert_eq!(best_score(&[1.0, 0.0], &[]), f32::NEG_INFINITY);
    }

    #[test]
    fn threshold_is_inclusive() {
        let enrolled = vec![vec![1.0, 0.0]];
        assert!(is_enrolled_voice(&[1.0, 0.0], &enrolled, 1.0));
        assert!(!is_enrolled_voice(&[0.0, 1.0], &enrolled, 0.0001));
    }

    #[test]
    fn best_of_several_enrollments_is_used() {
        let enrolled = vec![vec![0.0, 1.0], vec![1.0, 0.0]];
        assert!(close(best_score(&[1.0, 0.0], &enrolled), 1.0));
    }
}
