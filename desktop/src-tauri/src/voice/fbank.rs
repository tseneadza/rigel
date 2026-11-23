//! Kaldi-style 80-band log filter-bank features for the Wespeaker ECAPA model.
//!
//! Settings from the model's config.yaml: 80 mel bins, 25 ms frames, 10 ms shift.
//! Assumed, not yet checked against the reference implementation (the Mac
//! reference check does that): pre-emphasis 0.97, Povey window, no dither at
//! inference, and per-bin mean subtraction over time. The log floor and the
//! input scale do not change the result after mean subtraction.

use std::f32::consts::PI;

pub const SAMPLE_RATE: f32 = 16_000.0;
pub const NUM_MEL_BINS: usize = 80;
const FRAME_LEN: usize = 400; // 25 ms at 16 kHz
const FRAME_SHIFT: usize = 160; // 10 ms
const FFT_SIZE: usize = 512;
const PREEMPH: f32 = 0.97;

fn mel(hz: f32) -> f32 {
    1127.0 * (1.0 + hz / 700.0).ln()
}

/// Number of frames for `num_samples` (Kaldi snip-edges: only full frames).
pub fn frame_count(num_samples: usize) -> usize {
    if num_samples < FRAME_LEN {
        0
    } else {
        1 + (num_samples - FRAME_LEN) / FRAME_SHIFT
    }
}

fn povey_window() -> Vec<f32> {
    (0..FRAME_LEN)
        .map(|n| {
            let x = 2.0 * PI * n as f32 / (FRAME_LEN as f32 - 1.0);
            (0.5 - 0.5 * x.cos()).powf(0.85)
        })
        .collect()
}

/// Triangular mel weights, one row per mel bin, over the first FFT_SIZE/2 FFT bins.
fn mel_filters() -> Vec<Vec<f32>> {
    let low = 20.0_f32;
    let high = SAMPLE_RATE / 2.0;
    let (mlow, mhigh) = (mel(low), mel(high));
    let delta = (mhigh - mlow) / (NUM_MEL_BINS as f32 + 1.0);
    let bin_hz = SAMPLE_RATE / FFT_SIZE as f32;
    (0..NUM_MEL_BINS)
        .map(|i| {
            let left = mlow + i as f32 * delta;
            let center = left + delta;
            let right = center + delta;
            (0..FFT_SIZE / 2)
                .map(|j| {
                    let m = mel(bin_hz * j as f32);
                    let up = (m - left) / (center - left);
                    let down = (right - m) / (right - center);
                    up.min(down).max(0.0)
                })
                .collect()
        })
        .collect()
}

/// Power spectrum (|X|^2) of a power-of-two length real signal, bins 0..n/2.
fn power_spectrum(x: &[f32]) -> Vec<f32> {
    let n = x.len();
    debug_assert!(n.is_power_of_two());
    let mut re = x.to_vec();
    let mut im = vec![0.0_f32; n];
    let bits = n.trailing_zeros();
    for i in 0..n {
        let j = i.reverse_bits() >> (usize::BITS - bits);
        if j > i {
            re.swap(i, j);
            im.swap(i, j);
        }
    }
    let mut len = 2;
    while len <= n {
        let half = len / 2;
        for start in (0..n).step_by(len) {
            for k in 0..half {
                let (s, c) = (-2.0 * PI * k as f32 / len as f32).sin_cos();
                let (a, b) = (start + k, start + k + half);
                let tr = c * re[b] - s * im[b];
                let ti = c * im[b] + s * re[b];
                re[b] = re[a] - tr;
                im[b] = im[a] - ti;
                re[a] += tr;
                im[a] += ti;
            }
        }
        len <<= 1;
    }
    (0..n / 2).map(|k| re[k] * re[k] + im[k] * im[k]).collect()
}

/// Log mel filter-bank features, flattened as [frames * NUM_MEL_BINS] (row-major
/// by frame), with per-bin mean subtraction over time. Empty if too short.
pub fn fbank(samples: &[f32]) -> Vec<f32> {
    let frames = frame_count(samples.len());
    if frames == 0 {
        return Vec::new();
    }
    let window = povey_window();
    let filters = mel_filters();
    let mut out = vec![0.0_f32; frames * NUM_MEL_BINS];
    for f in 0..frames {
        let frame = &samples[f * FRAME_SHIFT..f * FRAME_SHIFT + FRAME_LEN];
        let mean = frame.iter().sum::<f32>() / FRAME_LEN as f32;
        let mut buf = vec![0.0_f32; FFT_SIZE];
        for n in 0..FRAME_LEN {
            let cur = frame[n] - mean;
            let prev = if n == 0 { cur } else { frame[n - 1] - mean };
            buf[n] = (cur - PREEMPH * prev) * window[n];
        }
        let spec = power_spectrum(&buf);
        for m in 0..NUM_MEL_BINS {
            let energy: f32 = filters[m].iter().zip(spec.iter()).map(|(w, p)| w * p).sum();
            out[f * NUM_MEL_BINS + m] = energy.max(f32::EPSILON).ln();
        }
    }
    for m in 0..NUM_MEL_BINS {
        let mean = (0..frames).map(|f| out[f * NUM_MEL_BINS + m]).sum::<f32>() / frames as f32;
        for f in 0..frames {
            out[f * NUM_MEL_BINS + m] -= mean;
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn frame_count_uses_only_full_frames() {
        assert_eq!(frame_count(399), 0);
        assert_eq!(frame_count(400), 1);
        assert_eq!(frame_count(559), 1);
        assert_eq!(frame_count(560), 2);
    }

    #[test]
    fn mel_scale_matches_the_standard_formula() {
        assert!((mel(700.0) - 1127.0 * 2.0_f32.ln()).abs() < 1e-3);
        assert!(mel(0.0).abs() < 1e-6);
    }

    #[test]
    fn impulse_has_a_flat_spectrum() {
        let mut x = vec![0.0_f32; FFT_SIZE];
        x[0] = 1.0;
        for p in power_spectrum(&x) {
            assert!((p - 1.0).abs() < 1e-4);
        }
    }

    #[test]
    fn a_tone_peaks_at_its_fft_bin() {
        // Bin 32 of a 512-point FFT: 32 * 16000 / 512 = 1000 Hz.
        let x: Vec<f32> = (0..FFT_SIZE)
            .map(|n| (2.0 * PI * 32.0 * n as f32 / FFT_SIZE as f32).cos())
            .collect();
        let spec = power_spectrum(&x);
        let peak = spec
            .iter()
            .enumerate()
            .max_by(|a, b| a.1.partial_cmp(b.1).unwrap())
            .unwrap()
            .0;
        assert_eq!(peak, 32);
    }

    #[test]
    fn every_mel_bin_has_a_filter() {
        for (i, row) in mel_filters().iter().enumerate() {
            assert!(row.iter().any(|&w| w > 0.0), "mel bin {i} is empty");
        }
    }

    #[test]
    fn output_has_one_row_per_frame_and_is_centred() {
        let samples: Vec<f32> = (0..16_000)
            .map(|n| (2.0 * PI * 440.0 * n as f32 / SAMPLE_RATE).sin() * 0.3)
            .collect();
        let feats = fbank(&samples);
        let frames = frame_count(samples.len());
        assert_eq!(feats.len(), frames * NUM_MEL_BINS);
        for m in 0..NUM_MEL_BINS {
            let mean: f32 = (0..frames).map(|f| feats[f * NUM_MEL_BINS + m]).sum::<f32>() / frames as f32;
            assert!(mean.abs() < 1e-3, "bin {m} not centred: {mean}");
        }
    }

    #[test]
    fn silence_and_too_short_input() {
        assert!(fbank(&[0.0; 100]).is_empty());
        let feats = fbank(&vec![0.0_f32; 1600]);
        assert!(feats.iter().all(|v| v.abs() < 1e-6));
    }
}
