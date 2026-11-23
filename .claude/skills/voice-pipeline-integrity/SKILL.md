---
name: voice-pipeline-integrity
description: >
  Required procedure for ANY change to Rigel's voice processing pipeline, audio
  configuration, microphone handling, STT/TTS integration, or voice quality
  validation: adding/editing audio input handlers, modifying STT/TTS providers,
  changing audio codec settings, updating noise filtering, debugging "voice not
  detected / speech unclear / audio broken" reports. Trigger on: voice,
  microphone, audio, STT, TTS, speech recognition, noise filter, audio codec,
  "voice not working", "can't hear", "speech unclear".
---

# Voice Pipeline Integrity — the audio quality triple-check

## Why this skill exists (the silent failure pattern)

Voice processing has multiple failure modes that don't surface as errors:
- Microphone input disabled or muted silently continues without warning
- STT provider changes affect transcription quality without alerts
- Audio codec mismatches cause degraded speech without crash logs
- Noise filtering too aggressive silently clips important audio
- TTS voice quality changes go unnoticed in non-interactive testing

These failures are **invisible in unit tests** and only appear in live usage. A
voice assistant with broken audio is unusable, but automated tests won't catch
it.

## The three voice quality checkpoints

| # | Component | File/Config | What it owns |
|---|-----------|-------------|--------------|
| 1 | Audio input | `src/voice/microphone.rs` or audio config | Microphone source, input validation, sample rate, bit depth |
| 2 | STT/TTS config | `src/voice/stt_config.toml` + `src/voice/tts_config.toml` | Provider credentials, model selection, language, audio format |
| 3 | Signal processing | `src/voice/processing/` + audio filters | Noise reduction, echo cancellation, gain normalization, codec choice |

**Audio changes touch all three in the same commit.** A new noise filter without
corresponding codec tests will cause silent quality degradation.

## Non-negotiable steps for any voice/audio change

1. **Run audio validation tests first and last:**
   ```bash
   cd src/voice && cargo test -- --include-ignored audio::tests
   cargo test -- --include-ignored pipeline::integration_tests
   ```
   These enforce: STT config←→codec parity, microphone input validation, noise
   filter effectiveness (measurable degradation floor), TTS output quality
   checks (pitch/speed ranges), end-to-end pipeline (input → process → output).

2. **Test with live microphone input:**
   - [ ] Run `cargo run --bin rigel-voice-test` with actual mic
   - [ ] Speak at normal volume, whisper, raised voice — all three
   - [ ] Test in quiet room AND with background noise
   - [ ] Verify STT accuracy hasn't degraded (baseline comparison)
   - [ ] Check TTS naturalness (not robotic, appropriate pacing)

3. **Audio config validation rules:**
   - Microphone sample rate must match STT input expectation (usually 16kHz)
   - Bit depth consistency: 16-bit PCM standard for STT, validate no 8-bit
   - Codec must support the speech profile (narrow-band vs wide-band)
   - Noise filter threshold must preserve speech frequencies (80Hz–8kHz)
   - Gain normalization range: -20dB to +20dB (beyond that = distortion)

4. **Provider configuration changes require verification:**
   - New STT provider: benchmark on reference audio clip (5+ sentences)
   - New TTS voice: record 3-minute sample, listen for artifacts
   - Provider credentials rotation: test with real API call, not mock
   - Rate limits: confirm new limits won't cause blocking during normal use

## "Voice not working" debugging order (before touching code)

1. **Microphone permission & status:**
   ```bash
   # Check if app has microphone permission
   # On macOS: System Preferences → Security & Privacy → Microphone
   # On Linux: Check PulseAudio/ALSA status: pactl list sources
   pkill -f rigel; sleep 2; cargo run --bin rigel  # Fresh start
   ```

2. **Audio input validation (is audio even reaching the pipeline?):**
   ```bash
   cargo run --bin voice-debug-input  # Dumps raw audio samples to file
   # If silent: microphone issue
   # If noise: filter too aggressive
   # If distorted: gain too high
   ```

3. **STT pipeline check:**
   ```bash
   cargo test stt::provider_test -- --nocapture
   # Verify STT provider responds to audio
   # Check API credentials are loaded
   ```

4. **TTS pipeline check:**
   ```bash
   cargo test tts::output_test -- --nocapture
   # Verify TTS provider can generate speech
   # Listen for audio output (check speaker volume/mute)
   ```

5. **Only then suspect the signal chain:**
   ```bash
   cargo run --bin voice-analyze-pipeline  # Visualize audio at each stage
   # Check filter output isn't clipping or silent
   ```

## Definition of done for voice/audio work

- [ ] All audio validation tests pass: `cargo test audio:: -- --include-ignored`
- [ ] Live microphone test completed with 3 volume levels & background noise
- [ ] STT/TTS config changes documented in `VOICE_CONFIG.md`
- [ ] All three checkpoints (input, config, processing) updated together
- [ ] Microphone permissions not accidentally revoked
- [ ] Audio codec and sample rate match across all components
- [ ] Noise filter effectiveness verified (speech preserved, noise reduced)
- [ ] TTS naturalness spot-checked (not robotic, appropriate volume)
- [ ] Changes committed with audio test results in commit message

---

**Related:** [[intent-definition-integrity]] (voice commands depend on clean
audio), [[desktop-sidecar-communication]] (audio data must cross IPC boundary
cleanly)
