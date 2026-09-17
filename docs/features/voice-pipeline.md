# Feature: Voice I/O (wake word → speech-to-text → spoken reply)

## Overview
Rigel can be spoken to. Say the wake word you trained ("Rigel" by default,
but it's whatever you recorded), then your command; Rigel transcribes it,
runs it through the same brain typed messages use, and speaks the reply
aloud. Everything runs on-device: wake-word matching against your own
recordings, whisper.cpp for transcription, and macOS's built-in `say` for
speech. No accounts, no network calls, no audio leaves the machine.

## Status
- [ ] Planned
- [ ] In Development
- [x] Alpha/Beta — verified live end-to-end on 2026-09-17 with real
      speech ("Rigel … open Safari", "Who am I?"); not yet tested at
      whisper/raised volume or with TV/music in the room.
- [ ] Production

## User-Facing Description
- **Set-up once** (Settings ⚙ → Voice): record your wake phrase three
  times, download the ~148 MB speech model, tick **Listen for the wake
  word**. See [`docs/setup/voice.md`](../setup/voice.md).
- **Talk:** say the wake word, pause half a beat, say the command. The orb
  turns **orange** ("Listening…") while it records, then "Working…" while
  it transcribes and thinks, then **"Speaking…"** while the reply plays.
- **Rigel is deaf while it talks.** Wake-word detection is muted for the
  duration of a spoken reply plus 0.7 s, so it can't hear itself.
- **Typed replies stay silent** unless you tick *Also speak replies to
  typed messages*. Voice-initiated replies are always spoken.
- **Voice picker:** any installed macOS voice (`say -v ?`), with a Test
  button.

## Technical Implementation

### Architecture
All audio work lives in the native Rust process (`desktop/src-tauri/src/voice/`).
The Python sidecar only ever sees final text, exactly as it does for typed
input — `brain.py` and the chat endpoint were not touched.

```
mic (cpal, native rate) ──► rustpotter (wake-word DTW match, own VAD gate)
                                   │ hit
                                   ▼
                     record until 1.2 s of silence (adaptive RMS VAD)
                     ├─ nothing above the speech threshold? drop it, back to idle
                     ▼
                     whisper.cpp (ggml-base.en) ──► reject "[BLANK_AUDIO]"-style output
                                   │ text
                                   ▼  Tauri event  voice://transcript
                     App.jsx ──► sendChat(text) ──► sidecar /api/rigel/chat (unchanged)
                                   │ reply
                                   ▼  Tauri command voice_speak
                     /usr/bin/say  ──► speech gate mutes the listener until done + 0.7 s
```

### Key Components
- **Native (Rust):** `voice/listener.rs` (always-on thread: wake word →
  record → transcribe state machine), `voice/enroll.rs` (records and
  silence-trims the wake-word samples, builds `~/.rigel/wakeword.rpw`),
  `voice/stt.rs` (whisper model download + transcription + non-speech
  filter), `voice/tts.rs` (`say` wrapper, emits `speaking`/`idle`),
  `voice/capture.rs` (one-shot recording for enrollment), `voice/mod.rs`
  (enable/disable commands + the TTS↔listener speech gate).
- **Frontend:** `desktop/src/voice.js` (typed wrappers for every voice
  command/event, `subscribeInEffect`, `looksLikeSpeech`), `App.jsx`
  (transcript → chat → speak, orb state), `SettingsPanel.jsx` (Voice tab).
- **Sidecar:** `VoiceConfig` model + `GET/POST /api/rigel/settings/voice-config`
  — see [`docs/api/voice-settings-endpoints.md`](../api/voice-settings-endpoints.md).
- **Storage:** `voice_config` in the `settings` table; on disk
  `~/.rigel/wakeword.rpw` (wake-word reference), `~/.rigel/models/ggml-base.en.bin`
  (speech model), `~/.rigel/debug/*.wav` (last enrollment + last 12
  captured utterances, for diagnosis).
- **Permissions:** `NSMicrophoneUsageDescription` in
  `desktop/src-tauri/Info.plist`; `core:event:default` in
  `capabilities/default.json` (required for JS `listen()` — without it
  events silently never arrive).

### Data Flow
1. Listener thread feeds the mic into rustpotter in exact
   `get_samples_per_frame()` chunks (it silently ignores any other size).
2. On a hit it emits `voice://state {recording}` and records until 1.2 s
   of quiet after speech was heard (or 12 s hard cap). If speech never
   crossed the threshold within 2.5 s, the recording is discarded.
3. Audio is downmixed/resampled to 16 kHz mono and transcribed on a
   worker thread; `[BLANK_AUDIO]`, `(silence)` and similar are rejected.
4. `voice://transcript {text}` → `App.jsx` posts it to `/api/rigel/chat`
   and appends both turns to the transcript, exactly like typed input.
5. The reply goes to `voice_speak`, which sets the speech gate, spawns
   `say`, and clears the gate (plus a 0.7 s cooldown) when it exits.

## Configuration
Persisted via Settings → Voice (no env vars):
```json
{ "tts_voice": "Samantha", "speak_typed_replies": false, "enabled": true }
```
Tunables are constants at the top of `listener.rs` (speech floor 0.003,
6× noise floor, 1.2 s hangover, 2.5 s onset grace, 12 s cap) and
`enroll.rs` (trim thresholds). rustpotter runs at library defaults
(threshold 0.5, avg 0.2) with `VADMode::Easy`.

## Usage Examples

### User Perspective
```
You:   "Rigel" … "open Safari"
Orb:   orange → "Working…" → "Speaking…"
Rigel: (aloud) "Understood. I would open app — but command execution is
        not wired up yet, so I've logged the intent instead. What's next?"
```

### Developer Perspective
```js
import { onTranscript, speak } from "./voice.js";
const unlisten = await onTranscript(({ text }) => console.log("heard:", text));
await speak("Hello there", "Samantha");
```

## Testing
- **Unit tests:** `cd desktop/src-tauri && cargo test --lib voice::` —
  silence trimming (incl. click rejection) and the non-speech text filter.
- **Real-audio check:** `cargo test --lib real_audio -- --ignored --nocapture`
  runs the trim over the last enrollment recordings in `~/.rigel/debug/`.
- **Manual checklist (live, 2026-09-17):**
  - [x] Wake word fires on the trained voice at normal volume (scores
        0.54–0.61 vs 0.5 threshold, three for three).
  - [x] Stays quiet through idle room noise and normal conversation.
  - [x] Command transcribed correctly ("Open Safari.", "Who am I?").
  - [x] Reply spoken; no re-trigger from Rigel's own voice.
  - [x] Window does not shrink/restore during a voice exchange.
  - [ ] Whispered / raised voice.
  - [ ] TV or music in the room.
  - [ ] Mic permission denied → clear in-app message.

## Known Limitations
- Wake word is speaker- and mic-specific: re-record if you switch mics
  (headset vs. built-in report very different levels).
- CPU-only whisper (the `metal` feature crashes at process exit); ~1 s per
  command on Apple Silicon.
- Enrollment and listening both open the default input; don't enrol while
  listening is on (Settings handles this by design order, not by lock).
- The permission-denied state has no dedicated UI yet.

## Future Enhancements
- Multi-word phrases / more enrollment samples for robustness.
- Barge-in (interrupt Rigel mid-sentence).
- Metal-accelerated whisper once upstream fixes the teardown crash.

## Related Features
- [Orb minimize / expand](orb-minimize.md) — why the window no longer
  shrinks for short exchanges.
- [LLM brain](llm-brain.md) — what the transcript is fed into.

## References
- [`docs/architecture/voice-pipeline.md`](../architecture/voice-pipeline.md)
- [`docs/troubleshooting/voice-pipeline.md`](../troubleshooting/voice-pipeline.md)
- [rustpotter](https://github.com/GiviMAD/rustpotter) ·
  [whisper-rs](https://github.com/tazz4843/whisper-rs) ·
  [cpal](https://github.com/RustAudio/cpal)
