# Setup Guide: Voice (wake word, speech-to-text, spoken replies)

## Overview
Turns on Rigel's always-on voice loop: say your wake word, speak a
command, hear the reply. Everything is local. Assumes the main
[Quick Start](../../README.md#-quick-start) is done and you're running
the **native app** (voice is unavailable in the plain browser preview).

## Prerequisites
- macOS (uses the built-in `say` for speech; Apple Silicon recommended
  for ~1 s transcription).
- A microphone. Use the one you'll keep using — the wake word is trained
  per mic.
- ~150 MB disk for the speech model, one-time download.
- Build tools if compiling yourself: Rust toolchain plus `cmake`
  (whisper.cpp is compiled into the app).

## Steps

### 1. Build and sign
```bash
cd desktop
npm run tauri build            # or: npm run tauri build -- --debug
codesign --force --deep -s - --identifier com.tonyseneadza.rigel \
  src-tauri/target/release/bundle/macos/Rigel.app
```
The re-sign matters: without a stable identifier macOS forgets the mic
grant on every rebuild and feeds the app silence. Install by copying
`Rigel.app` to `/Applications` (quit any running copy first).

### 2. Grant the microphone
Launch Rigel. The first time it opens the mic, macOS asks for permission
(the reason text comes from `desktop/src-tauri/Info.plist`). If you
declined earlier: System Settings → Privacy & Security → Microphone →
enable Rigel, then relaunch.

### 3. Settings ⚙ → Voice
1. **Record wake phrase.** You'll be prompted three times; say the word
   at normal volume each time the prompt appears (there's a 1.5 s
   lead-in). Enrollment trims each take to the spoken word and refuses a
   take where it heard nothing — just try that one again.
2. **Download model** (`ggml-base.en.bin`, ~148 MB, from Hugging Face).
3. Tick **Listen for the wake word.** Applies and saves immediately.
4. Optionally pick a **voice** and press **Test**; tick *Also speak
   replies to typed messages* if you want that. Press **Save** for these.

### 4. Try it
Say the wake word, pause half a beat, then "open Safari". The orb goes
orange while you speak, "Working…" briefly, then the reply is spoken.

## Where things live
| Path | What |
|------|------|
| `~/.rigel/wakeword.rpw` | Your wake-word reference (delete via *Reset* in Settings). |
| `~/.rigel/models/ggml-base.en.bin` | Speech model. |
| `~/.rigel/debug/` | Last enrollment takes and last 12 captured utterances, for diagnosis. |
| `~/Library/Logs/com.tonyseneadza.rigel/Rigel.log` | Detection scores, recording levels, transcripts. |

## Gotchas
- **Switched mics?** Re-record the wake phrase.
- **Rebuilt the app?** Re-sign it (step 1) or the mic goes silent.
- **Using `/Applications/Rigel.app`?** Rebuilding `target/…` does nothing
  until you copy the new bundle over and relaunch.
- **Dev preview in a browser:** every voice call is a no-op there.

If something doesn't work, go straight to
[`docs/troubleshooting/voice-pipeline.md`](../troubleshooting/voice-pipeline.md)
— it's written around the log lines and files above.
