#!/usr/bin/env python3
"""Reference check for Rigel's fbank frontend and the Wespeaker ECAPA model.

Usage:
  python3 tools/speaker_ref_check.py <sample.wav> <voxceleb_ECAPA512_LM.onnx> <out_dir>

Writes into <out_dir>:
  ref_fbank.txt      frames * 80 floats, row-major, Kaldi fbank with CMN
  ref_embedding.txt  the model's embedding for the same features

Needs: pip install torch torchaudio onnxruntime
"""
import pathlib
import sys

import wave

import numpy as np
import onnxruntime as ort
import torch
import torchaudio

wav_path, model_path, out_dir = sys.argv[1:4]
out = pathlib.Path(out_dir)
out.mkdir(parents=True, exist_ok=True)

# Read the 16-bit PCM WAV with the stdlib (torchaudio.load needs torchcodec here).
with wave.open(wav_path, "rb") as w:
    sr, channels, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
    raw = w.readframes(w.getnframes())
assert sr == 16000, f"expected 16 kHz, got {sr}"
assert channels == 1, "expected mono"
assert width == 2, "expected 16-bit PCM"
pcm = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
wave_t = torch.from_numpy(pcm).unsqueeze(0)  # [1, samples], float32 in [-1, 1]

# Wespeaker scales to int16 range before Kaldi fbank; no dither at inference.
feats = torchaudio.compliance.kaldi.fbank(
    wave_t * (1 << 15),
    num_mel_bins=80,
    frame_length=25.0,
    frame_shift=10.0,
    dither=0.0,
    sample_frequency=16000,
    window_type="povey",
    use_energy=False,
)
feats = feats - feats.mean(dim=0, keepdim=True)  # per-bin mean subtraction over time

(out / "ref_fbank.txt").write_text(" ".join(f"{v:.8g}" for v in feats.flatten().tolist()))

sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
input_name = sess.get_inputs()[0].name
emb = sess.run(None, {input_name: feats.unsqueeze(0).numpy()})[0].flatten()
(out / "ref_embedding.txt").write_text(" ".join(f"{v:.8g}" for v in emb.tolist()))

print(f"frames={feats.shape[0]} bins={feats.shape[1]} embedding_dims={emb.shape[0]} input={input_name}")
print(f"wrote {out / 'ref_fbank.txt'} and {out / 'ref_embedding.txt'}")
