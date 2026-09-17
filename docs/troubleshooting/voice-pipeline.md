# Troubleshooting Guide: Voice Pipeline

Debug from evidence, not code-reading. Every symptom below has a log line
or a file that proves or disproves it.

**Evidence sources**
- App log: `~/Library/Logs/com.tonyseneadza.rigel/Rigel.log`
  (`grep -v "still listening"` to hide the 20-second status heartbeat).
- Audio the pipeline actually saw: `~/.rigel/debug/` — the last
  enrollment (`enroll_N_raw.wav`, `enroll_N_trimmed.wav`) and the last 12
  captured utterances (`utt_<ms>_speech.wav` / `_nospeech.wav`).
- What reached the brain: `curl -s localhost:5140/api/rigel/logs?limit=10`
  (timestamps are UTC).
- Which binary is running: `pgrep -fl "Rigel.app/Contents/MacOS/app"` —
  an installed `/Applications/Rigel.app` is not the `target/…/Rigel.app`
  you just built.

## Quick Diagnosis

```
Nothing happens when you say the wake word?
│
├─ No "voice listener: mic …Hz" line in the log at all?
│  → listener never started: wake word not trained, model not downloaded,
│    or "Listen for the wake word" unticked. Settings → Voice shows which.
│
├─ Listener started, but "still listening, mic rms=0.00000" forever?
│  → the mic is muted by macOS. See "Mic silently muted (TCC)".
│
├─ Mic has level, still no "wake word detected"?
│  → wake word trained on a different mic or on silence.
│    See "Wake word doesn't fire on my voice".
│
└─ "wake word detected" appears, orb never turns orange?
   → events aren't reaching the webview. See "Backend works, UI doesn't".

Rigel triggers on nothing / talks to itself?
│
├─ Sidecar log shows "[BLANK_AUDIO]" turns seconds apart?
│  → the speech gate isn't in this build, or `stt:` lines show blank text
│    passing through. See "Feedback loop".
│
└─ Detections logged with score ≈ 0.50–0.52 while no one spoke?
   → wake-word reference contains too much silence. Re-record.
```

## Common Issues

### Issue: Mic silently muted (TCC / code signature)
**Symptoms:** listener starts, every status line says `mic rms=0.00000`,
no permission dialog appears.

**Diagnosis:** `codesign -dv /path/to/Rigel.app 2>&1 | grep Identifier`.
An identifier like `app-3338545feff32015` is a content hash that changes
every build; macOS tied the microphone grant to a different one and now
feeds the app zeros rather than erroring.

**Fix:**
```bash
codesign --force --deep -s - --identifier com.tonyseneadza.rigel <Rigel.app>
```
after every rebuild, then relaunch. Check the grant in System Settings →
Privacy & Security → Microphone if it still reads zero.

### Issue: Wake word doesn't fire on my voice
**Symptoms:** mic level moves when you speak (status lines show
`rms=0.02–0.1`), no `wake word detected`.

**Diagnosis:**
1. Which mic is the listener on? The start line says e.g. `mic 48000Hz/1ch`.
   The earlier session used a 16 kHz input (headset) and later the 48 kHz
   built-in mic; the reference is mic-specific.
2. What did enrollment capture? Compare `enroll_N_raw.wav` vs
   `enroll_N_trimmed.wav`; trimmed should be ~0.6–1.0 s of the word.
   `cd desktop/src-tauri && cargo test --lib real_audio -- --ignored --nocapture`
   prints the trim result for each raw file.

**Fix:** Settings → Voice → **Re-record wake phrase** on the mic you'll
use, speaking at normal volume when the prompt appears. Enrollment now
refuses a sample in which it heard nothing.

### Issue: False triggers on background noise
**Symptoms:** `wake word detected — score=0.50…` lines with nobody
speaking; the matching recording is `utt_*_nospeech.wav` or the log says
`gave up waiting for speech`.

**Diagnosis:** look at `per_ref=[…]` in the detection line. Scores barely
over 0.5 on all three references, while genuine hits score 0.54–0.61 on
at least one, indicate a reference dominated by silence (recorded before
the trimming fix, or with the word too far from the mic).

**Fix:** re-record. If it persists on a very noisy mic, raise
`rp_config.detector.threshold` in `listener.rs` in 0.05 steps and
compare genuine-hit scores in the log before and after.

### Issue: Feedback loop — Rigel keeps saying `Received: "[BLANK_AUDIO]"`
**Symptoms:** sidecar log fills with `[BLANK_AUDIO]` user turns 8–25 s
apart; app log alternates `wake word detected` / `recording ended (gave
up waiting for speech)`.

**Diagnosis:** the listener heard Rigel's own reply through the speakers.
In a current build the log shows `muted while speaking` right after each
`transcript =` line and `unmuted, detector reset` after the reply; if
those lines are missing, the running binary predates the speech gate
(check `pgrep -fl` for the path and its mtime).

**Fix:** install/relaunch the current build. Blank transcripts are now
dropped at three layers (whisper `suppress_nst`, `stt.rs::looks_like_speech`,
`voice.js::looksLikeSpeech`) and no-speech recordings never reach whisper.

### Issue: Backend works, UI never changes (orb never orange)
**Symptoms:** log shows detections and `transcript = "…"`, sidecar has
the turn, but the orb stays blue and nothing is spoken.

**Diagnosis:** Tauri v2 — JS `listen()` needs `core:event:default` in
`desktop/src-tauri/capabilities/default.json`; without it events are
dropped silently while `invoke()` still works.

**Fix:** confirm the permission is present, rebuild.

### Issue: Recording cuts off before the command / transcribes only "Rigel"
**Symptoms:** `recording ended (went quiet)` with `< 1 s captured`, or
transcripts that start with the wake word.

**Diagnosis:** `SPEECH_ONSET_GRACE` (2.5 s) covers the pause after the
wake word; if you pause longer, the recording is dropped as `gave up
waiting`. The wake-word audio itself is excluded by design (recording
seeds from the frame-buffer remainder after the matching frame).

**Fix:** speak the command within ~2 s of the wake word, or raise the
grace constant.

### Issue: Window disappears and reappears during a voice command
**Symptoms:** on each command the whole window shrinks to a small square
for under a second, then restores.

**Diagnosis:** the auto-minimize used to fire the instant `orbState`
became `thinking`; a voice round trip is faster than that looks good.

**Fix:** current builds require 2.5 s of continuous work before
shrinking (`WORKING_MINIMIZE_DELAY_MS` in `App.jsx`). See
[`orb-minimize.md`](orb-minimize.md).

### Issue: Log is empty or keeps losing history
**Symptoms:** `Rigel.log` is 0 bytes or only holds the last few minutes.

**Diagnosis:** older builds enabled logging only in debug profiles and
used the plugin's default 40 KB cap with a one-per-second status line.

**Fix:** current builds log in release too, cap at 20 MB, keep 3 rotated
files, and emit the status line every 20 s.

### Issue: Build fails resolving `rand` / `half` / `candle-core`
**Fix:** keep `half = "=2.4.1"` pinned in `Cargo.toml` — the comment there
explains the rustpotter → candle-core → rand version split.

### Issue: App crashes at exit after transcribing
**Diagnosis:** the `metal` feature of `whisper-rs` asserts in ggml's
Metal teardown. **Fix:** build without it (the default in `Cargo.toml`).

## Verifying a fix
1. Confirm the running process is the new binary (path + mtime).
2. Say the wake word once and read the detection line's `score`.
3. Open the newest `utt_*_speech.wav` and check it contains your command,
   not silence or Rigel's voice.
4. Check the sidecar turn text matches what you said.
Only then call it fixed.
