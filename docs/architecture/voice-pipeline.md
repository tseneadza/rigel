# Architecture: Voice Pipeline

## Overview
How Rigel hears, understands, and speaks — and the decisions behind it.
Companion to [`docs/features/voice-pipeline.md`](../features/voice-pipeline.md)
(what the user sees) and
[`docs/troubleshooting/voice-pipeline.md`](../troubleshooting/voice-pipeline.md)
(what to do when it doesn't).

## Components

```
desktop/src-tauri/src/voice/
├── mod.rs        voice_set_enabled / voice_is_enabled; SpeechGate (TTS ↔ listener)
├── listener.rs   the always-on thread: Listening ⇄ Recording state machine
├── enroll.rs     3× record → trim_to_speech → rustpotter WakewordRef → ~/.rigel/wakeword.rpw
├── stt.rs        whisper model download; transcribe(); looks_like_speech()
├── tts.rs        /usr/bin/say child process; emits voice://state speaking|idle
└── capture.rs    record_seconds() — one-shot capture used by enrollment

desktop/src/voice.js          JS wrappers; subscribeInEffect(); looksLikeSpeech()
desktop/src/App.jsx           transcript → sendChat → handleExchange(…, "voice") → speak
sidecar/app.py                VoiceConfig + /settings/voice-config (preferences only)
```

## Design Decisions

### Audio stays in the native process
The sidecar receives text only. Streaming PCM over HTTP to Python would
have added latency, a second audio stack, and a protocol; instead the
Tauri process owns mic, wake word, STT and TTS, and the existing
`/api/rigel/chat` path is reused unchanged. Typed and spoken input are
indistinguishable to the brain.

### Wake word: rustpotter *reference* mode, trained from the user's voice
No pretrained "Hey Rigel" model exists. rustpotter compares live MFCC
frames against 3–8 recordings via dynamic time warping. Consequences:
- The reference is built from the **whole** file — rustpotter does no
  endpointing. Untrimmed 2.5 s samples (~80 % silence) produced a matcher
  that recognised silence: it fired on background noise and missed the
  real word. `enroll.rs::trim_to_speech` therefore anchors on the loudest
  20 ms window and grows outward while the level stays above
  `max(0.002, 4 × floor, 0.12 × peak)`, tolerating 200 ms gaps, then pads
  150 ms. On real recordings this cuts 2.5 s → ~0.8 s.
- `process_samples()` returns `None` (no error) unless given exactly
  `get_samples_per_frame()` samples. cpal delivers whatever the OS
  chooses, so `listener.rs` re-chunks through a frame buffer.
- rustpotter's own adaptive VAD (`VADMode::Easy`) is enabled so silent
  frames are never scored. Thresholds stay at library defaults (0.5 /
  0.2); loosening them was tried and only produced noise triggers.

### Recording end-pointing: adaptive RMS, not a fixed number
Idle mic RMS was 0.0003 on one input device and 0.002 on another; a fixed
0.01 threshold was wrong for both. The listener tracks a slow noise-floor
EMA while idle (seeded only from a non-zero chunk) and uses
`max(0.003, 6 × floor)` as the speech threshold. Recording ends 1.2 s
after the last speech chunk, or after 2.5 s if speech never started (that
recording is **dropped**, not transcribed), or at 12 s.

### The speech gate (why Rigel can't hear itself)
The mic hears the speakers. Before the gate existed, a spoken reply →
false wake → silent recording → whisper's `[BLANK_AUDIO]` → sent to the
brain → spoken → loop, visible in the sidecar log as blank turns 8–25 s
apart. `voice::tts_started()` is called before `say` spawns and
`tts_finished()` when it exits or is killed; `tts_blocks_listening()` is
true for that span plus 0.7 s. While blocked the listener discards audio,
and on unblock it resets rustpotter so no TTS tail is in its window.

Belt-and-braces on the same failure: whisper runs with `suppress_nst`
and `suppress_blank`, `stt.rs::looks_like_speech` rejects bracketed /
letter-less output, and `voice.js::looksLikeSpeech` repeats the check in
JS before anything reaches the sidecar.

### Recording starts *after* the wake word
On a hit, the un-drained remainder of the frame buffer (audio after the
frame that completed the match) seeds the recording; the drained frames
(the wake word itself) are not included, so whisper doesn't transcribe
"Rigel open Safari".

### CPU-only whisper
`whisper-rs` with the `metal` feature transcribes fine but asserts in
ggml's Metal residency-set teardown at process exit (reproduced twice
with the canonical JFK sample). CPU-only exits cleanly; ~1 s per short
command on Apple Silicon is acceptable.

### Tauri v2 specifics that bit
- `core:event:default` must be in `capabilities/default.json` or JS
  `listen()` silently receives nothing while `invoke()` keeps working.
- Ad-hoc code signing produces a content-hash identifier per build;
  macOS TCC ties the mic grant to that identity and **silently mutes**
  the mic for an "unknown" app. Re-sign with
  `codesign --force --deep -s - --identifier com.tonyseneadza.rigel`.
- The log plugin's default 40 KB rotation threw away evidence within
  minutes; it's now 20 MB × 3 files and enabled in release builds too.

## State Machine

```
              tts_blocks_listening()          rustpotter hit
 Listening ──────────────────────► (deaf) ──┐   │  emit recording
     ▲  ◄────────── reset ◄─────────────────┘   ▼
     │                                     Recording{heard_speech}
     │   no speech in 2.5 s → drop, emit idle    │ 1.2 s quiet after speech / 12 s cap
     └───────────────────────────────────────────┤
                                                 ▼  emit thinking
                                          stt::transcribe (worker thread)
                                           ├─ non-speech → emit idle
                                           └─ text → emit voice://transcript
```
Orb state on the frontend: `idle | recording | thinking | speaking`.
"idle" events are ignored while a chat request is in flight (separate
busy flags for typed and voice so one can't un-guard the other).

## Alternative Approaches Considered
- **Cloud STT/TTS** — rejected: the product framing is local execution;
  also latency and accounts.
- **Push-to-talk** — the user chose always-on. The gate + VAD work above
  is the price of that choice.
- **Shipping a trained `.rpw`** — nothing exists for "Rigel"; per-user
  enrollment doubles as speaker adaptation.
- **Fixed VAD threshold** — see above; two real mics disagreed by 7×.

## Diagnostics built in
- `~/Library/Logs/com.tonyseneadza.rigel/Rigel.log`: listener start
  (mic Hz/ch, detector config), each detection's `score/avg_score/per_ref`,
  recording end stats (`peak_chunk`, `p95_chunk`, `speech_threshold`,
  `heard_speech`), whisper output with `no_speech_prob`, mute/unmute.
- `~/.rigel/debug/`: `enroll_N_raw.wav` / `enroll_N_trimmed.wav` and the
  last 12 `utt_<ms>_{speech|nospeech}.wav`. Float32 WAVE_FORMAT_EXTENSIBLE
  — Python's `wave` module can't open them; parse the RIFF chunks directly.
