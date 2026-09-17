# Glossary & Technical Terms

A reference for the vocabulary used across Rigel's code, docs, and commit
history — product concepts (the orb, the HUD), architecture components
(desktop shell, sidecar, brain), the data model, and the voice pipeline.
Terms are grouped by area; each entry links to the file(s) or doc where it's defined or used in
depth.

---

## Product Concepts

**Rigel**
The project itself: a voice-activated, autonomous desktop agent with a
JARVIS-style holographic HUD, named after the blue supergiant star in
Orion. See [`README.md`](../README.md).

**Orb** (a.k.a. **presence orb**, **RigelOrb**)
The single central visual element of Rigel's UI — a luminous, breathing
ice-blue sphere rendered as a 3D Bohr-style atom (white-hot nucleus,
layered glow, expanding ripple rings, three electrons on tilted orbits).
It is Rigel's only always-visible surface; the chat console and header
appear around it and can be hidden while it stays on screen. Implemented
in [`desktop/src/components/RigelOrb.jsx`](../desktop/src/components/RigelOrb.jsx).

**HUD** (Heads-Up Display)
The overall holographic-style visual interface Rigel presents — the orb
plus the console/header chrome around it — styled after the "blazing
blue," high-contrast aesthetic described in the README.

**Navigational anchor**
The README's framing for the orb's role: the fixed point the user looks to
in order to act on the OS, replacing manual folder/menu navigation.

**Deep-space look**
The window's visual treatment: a solid black background with a scattered
starfield and soft nebula glow behind the orb — opaque, never transparent
to the desktop. See
[`docs/features/orb-minimize.md`](features/orb-minimize.md) and
[`docs/architecture/orb-minimize-state.md`](architecture/orb-minimize-state.md)
(the "Alternative Approaches" section documents why a click-through,
transparent window was tried and rejected).

**Orb state**
One of `"idle" | "recording" | "thinking" | "speaking"`, passed as the
`state` prop to `RigelOrb`. Drives the orb's hue via a single CSS custom
property (`--orb`, an `"r,g,b"` triple): ice-blue idle, **orange while
recording a spoken command**, thinking while a chat request or
transcription is in flight, and speaking while a reply is read aloud.
`recording`/`speaking` are emitted by the native voice pipeline as
`voice://state` events; `thinking` comes from both the chat lifecycle and
the pipeline.

**Caption**
The short status line rendered under the orb (default `"Standing by."`),
independent of chat transcript text.

**Command intent** (a.k.a. **intent**)
A structured `{action, args}` object Rigel detects from user text — the
thing Rigel *would* execute if the OS-hook execution layer existed yet.
See [Command Intent](#command-intent-1) under Data Model for the full
definition, and
[`docs/TEMPLATE-COMMAND-INTENT.md`](TEMPLATE-COMMAND-INTENT.md) for how to
document a new intent type.

---

## Architecture Components

**Desktop shell** (a.k.a. **desktop app**)
The Tauri + React front end: the orb, chat console, settings panel, and
native window management. Lives in [`desktop/`](../desktop/), served at
`http://localhost:1425` in dev.

**Sidecar**
The local Python FastAPI service Rigel's desktop shell talks to over HTTP.
Owns Rigel's private SQLite log/memory store and the brain (reply +
command-intent logic). Lives in [`sidecar/`](../sidecar/), runs on port
`5140` by default. Named and structured after (but sharing no runtime or
database with) AgenticOS's own sidecar — see the docstring in
[`sidecar/app.py`](../sidecar/app.py).

**Tauri**
The Rust-based framework that wraps the React front end in a native,
borderless desktop window and exposes OS-level APIs (window
sizing/positioning, global shortcuts) to JavaScript. Config lives in
`desktop/src-tauri/`.

**Brain**
The module that turns user text into `(reply, commands)` —
[`sidecar/brain.py`](../sidecar/brain.py). Dispatches to a configured LLM
provider (Claude or Ollama) or falls back to a deterministic regex stub.
See [`docs/features/llm-brain.md`](features/llm-brain.md).

**Provider**
One of `"stub" | "claude" | "ollama"` — which backend `brain.respond()`
uses to generate a reply and detect commands. Selected in Settings → Brain
and persisted as part of `llm_config`. See
[`docs/architecture/llm-provider-selection.md`](architecture/llm-provider-selection.md).

**Stub**
The original regex-based responder (`_stub_respond` in `brain.py`) —
pure, deterministic, no network calls. Used when no LLM provider is
configured, and as the automatic fallback when a configured provider
fails.

**LLMError**
The single exception type both LLM providers (`claude_respond`,
`ollama_respond`) raise on any failure (auth, network, bad JSON, missing
credentials, unreachable host). `brain.py` only needs one `except` clause
because of this. Defined in
[`sidecar/llm_providers.py`](../sidecar/llm_providers.py).

**Structured outputs**
The Claude API feature (`output_config: {format: {type: "json_schema",
...}}`) used by `claude_respond()` to force a parseable JSON reply instead
of free-form text. See the "Alternative Approaches Considered" section of
[`docs/architecture/llm-provider-selection.md`](architecture/llm-provider-selection.md).

**Probe** (as in `probe_ollama`)
A live check of a local Ollama install — which models are pulled, their
on-disk size, and whether they'll fit this machine's RAM — used to power
the Settings UI's model picker rather than a hardcoded model list.

**IPC** (Inter-Process Communication)
Here: the two separate channels Rigel's processes use to talk —
Tauri↔React IPC inside the desktop shell (e.g. `@tauri-apps/api/window`
calls), and HTTP between the desktop shell and the sidecar (`/api/rigel/*`).

---

## Data Model

All persistent state lives in one SQLite database, described in full by
[`sidecar/db.py`](../sidecar/db.py).

**`~/.rigel/rigel.db`**
The database file itself — user-scoped (outside the repo), one file per
machine. Overridable via the `RIGEL_DB` environment variable (tests point
this at a temp file).

**Turn**
One row in the `turns` table: a single conversation message, `role` is
either `"user"` or `"rigel"`. Every chat message — both sides — is logged
here, one turn per message, from day one.

**Command attempt** <a id="command-intent-1"></a>
One row in the `command_attempts` table: a logged record of a command
intent Rigel detected, linked to the `turn_id` that triggered it, with an
`action` (e.g. `open_app`, `close_app`, `create_file`, `delete_file`), a
JSON `args` blob (e.g. `{"target": "VS Code"}`), and a `status`. Distinct
from a "command intent" in memory (the `{action, args}` dict `brain.py`
returns) — a command attempt is that intent's persisted, logged form.

**Status** (of a command attempt)
One of `"deferred" | "ok" | "blocked" | "error"`. Every command Rigel
detects today is logged as `"deferred"`, since the OS-hook execution layer
isn't wired up yet — logging happens regardless of whether execution ever
runs.

**Setting**
One row in the `settings` table: a `key` → JSON `value` pair with a
`last_updated` timestamp, upserted via `set_setting()`. The three settings
Rigel currently persists are `orb_config`, `llm_config` and `voice_config`.

**`orb_config`**
The persisted setting controlling the orb's saved size and position:
`diameter_px` (60–620), `position_corner` (`"center" | "top-left" |
"top-right" | "bottom-left" | "bottom-right" | "custom"`), `is_minimized`,
and — when the corner is `"custom"` — `x_pct`/`y_pct` as percentages of the
window.

**`llm_config`**
The persisted setting controlling the brain's provider choice: `provider`,
`claude_model`, `ollama_model`, `ollama_host`.

**`voice_config`**
The persisted voice preferences: `tts_voice` (macOS voice name or null),
`speak_typed_replies`, `enabled` (start wake-word listening at launch).
Preferences only — the wake-word reference and speech model are files
under `~/.rigel/`, owned by the native app. See
[`docs/api/voice-settings-endpoints.md`](api/voice-settings-endpoints.md).

---

## Desktop / Window Terms

See [`docs/architecture/orb-minimize-state.md`](architecture/orb-minimize-state.md)
for the full state machine these terms belong to.

**Minimized**
The derived boolean (`App.jsx`) that decides whether Rigel shows its full
window (header + orb + chat console) or just the orb. Computed as
`autoMinimized || manualMinimize` — an OR of a transient and a sticky
signal, never a single state machine, so a manual minimize always outlives
the request that may also have triggered it.

**`isWorking`** / **`autoMinimized`**
The transient half of `minimized`. `isWorking` is `true` while
`orbState === "thinking"` (a chat request or a transcription is in
flight). `autoMinimized` follows it only after **2.5 s of continuous
work** (`WORKING_MINIMIZE_DELAY_MS`), so a sub-second voice or typed round
trip never moves the window — shrinking and restoring for that read as
the window vanishing. `recording` deliberately does not minimize: the
orange orb is the "I heard you" cue.

**Busy flags** (`typedBusyRef`, `voiceBusyRef`)
Two independent refs in `App.jsx` marking an in-flight typed or voice
exchange. Their OR suppresses stray `idle` events (e.g. TTS finishing)
from clobbering `thinking`; they are separate so one flow finishing can't
un-guard the other.

**`manualMinimize`**
The sticky half of `minimized`: toggled only by the global hotkey, and
never reset just because a request finished.

**Global hotkey** (a.k.a. **accelerator**, **toggle hotkey**)
`Cmd/Ctrl+Shift+R` (accelerator string `"CmdOrCtrl+Shift+R"`) — toggles
`manualMinimize`. In the native app it's a true OS-level shortcut via
`@tauri-apps/plugin-global-shortcut`, firing even when Rigel isn't
focused. Outside Tauri (browser/dev preview) it falls back to a
window-scoped `keydown` listener. Implemented in
[`desktop/src/hotkey.js`](../desktop/src/hotkey.js).

**Resting bounds**
The window's size and position immediately before it last shrank to work,
remembered once (`nativeWindow.js`'s module-level `restingBounds`) so
repeated shrinks don't clobber it, and restored exactly by
`restoreRestingBounds()` once the reply lands.

**`shrinkToCorner` / `restoreRestingBounds`**
The two functions in [`desktop/src/nativeWindow.js`](../desktop/src/nativeWindow.js)
that resize and reposition the *actual OS window* (not just CSS) to a
small square anchored to the active monitor's bottom-right corner, and
back. No-ops outside a Tauri webview.

**Native window sync**
Shorthand for the behavior above: keeping the real OS window bounds in
step with the CSS-level minimize/expand state.

---

## Voice Terms

See [`docs/architecture/voice-pipeline.md`](architecture/voice-pipeline.md)
for how these fit together.

**Wake word** (a.k.a. **wake phrase**)
The word the user records three times in Settings → Voice ("Rigel" by
convention) that arms a spoken command. Matched on-device by rustpotter
against those recordings; nothing is transcribed until it fires.

**rustpotter**
The Rust wake-word library Rigel uses in *reference mode*: live audio is
converted to MFCC frames and compared by dynamic time warping against the
user's recordings — no neural net, no training data beyond enrollment.
Feed it exactly `get_samples_per_frame()` samples per call or it silently
does nothing.

**WakewordRef** / **`~/.rigel/wakeword.rpw`**
rustpotter's saved reference built from the trimmed enrollment samples —
the artefact `enroll.rs` writes and `listener.rs` loads.

**Enrollment**
The three-take recording flow (`voice/enroll.rs`) that produces the
wake-word reference. Each 2.5 s take is **trimmed** to the spoken word
first, because rustpotter does no endpointing and a reference that is
mostly silence matches silence.

**Trim** (`trim_to_speech`)
Enrollment's endpointing: anchor on the loudest 20 ms window, expand
while the level stays above `max(0.002, 4 × floor, 0.12 × peak)`
tolerating 200 ms gaps, pad 150 ms. Cuts a 2.5 s take to ~0.8 s.

**MFCC** (Mel-Frequency Cepstral Coefficients)
The compact per-frame spectral features (16 per frame here) rustpotter
compares; standard speech-recognition front-end.

**DTW** (Dynamic Time Warping)
The alignment algorithm rustpotter scores with — tolerant of the word
being said faster or slower than in the recordings.

**Detection score** (`score`, `avg_score`, `per_ref`)
Logged on every wake-word hit. `score` is the best match against any one
enrollment sample (threshold 0.5), `avg_score` the match against the
averaged template (threshold 0.2), `per_ref` the per-sample scores.
Genuine hits on the trained voice score ~0.54–0.61; noise triggers hover
at 0.50–0.52 across all samples.

**VAD** (Voice Activity Detection)
Two layers: rustpotter's own adaptive gate (`VADMode::Easy`) stops silent
frames being scored, and the listener's RMS-based end-pointing decides
when a command recording ends.

**RMS** (Root Mean Square)
The loudness measure used throughout the pipeline for audio in the
[-1, 1] float range. Idle room: ~0.0003 (headset) to ~0.002 (built-in
mic); normal speech: 0.03–0.1 per 100 ms.

**Noise floor** / **speech threshold**
A slow exponential average of idle chunk RMS tracked by the listener,
and the derived level a chunk must exceed to count as speech:
`max(0.003, 6 × noise_floor)`. Replaced a fixed 0.01 that suited neither
real mic.

**Speech-onset grace** (2.5 s), **silence hangover** (1.2 s), **hard cap** (12 s)
The three timers that end a command recording: give up if speech never
starts, stop after 1.2 s of quiet once it has, never record longer than
12 s. A recording that ends via the grace period is dropped, not
transcribed.

**STT** (Speech-to-Text) / **whisper.cpp** / **`ggml-base.en.bin`**
Transcription via `whisper-rs` bindings to whisper.cpp, CPU-only, using
the ~148 MB English base model downloaded once to `~/.rigel/models/`.
Runs with non-speech tokens suppressed.

**`[BLANK_AUDIO]`**
Whisper's hallucinated output for near-silent input (also `(silence)`,
`[MUSIC]`, …). Rejected by `stt.rs::looks_like_speech` and again by
`voice.js::looksLikeSpeech` so it never reaches the brain. Its appearance
in the sidecar log is the signature of the feedback loop below.

**TTS** (Text-to-Speech)
Spoken replies via macOS's `/usr/bin/say` (`voice/tts.rs`), voice
selectable in Settings. A new reply kills an in-flight one.

**Speech gate** (`tts_started` / `tts_finished` / `tts_blocks_listening`)
The shared flag in `voice/mod.rs` that makes the listener deaf while
Rigel speaks and for 0.7 s after. Prevents the **feedback loop**: reply
heard through the speakers → false wake → silent recording →
`[BLANK_AUDIO]` → sent to the brain → spoken → repeat.

**Speech gate cooldown**
The 0.7 s after `say` exits during which the listener stays deaf (speaker
tail, process teardown); on unmute rustpotter is reset.

**Listener**
The always-on native thread (`voice/listener.rs`) that runs the
`Listening ⇄ Recording` state machine and emits `voice://state`,
`voice://transcript`, `voice://error`.

**`voice://…` events**
Tauri events from native to webview: `state`, `transcript`, `error`,
`enroll-progress`, `enroll-done`, `model-download`. Require
`core:event:default` in `capabilities/default.json` — without it they
are silently dropped.

**`subscribeInEffect`**
`voice.js` helper for subscribing to a Tauri event inside a React effect
without leaking a duplicate listener when StrictMode/HMR tears the effect
down before `listen()` resolves.

**cpal**
The cross-platform Rust audio-capture crate the mic stream comes through
(CoreAudio on macOS). Reports the device's native rate/channels; the
pipeline adapts (48 kHz and 16 kHz mono both seen).

**TCC** (Transparency, Consent, and Control)
macOS's per-app permission system. It ties the microphone grant to the
app's code-signing identity; an ad-hoc build whose identifier changes
each rebuild is silently fed **zeros**, not an error — hence the
`--identifier com.tonyseneadza.rigel` re-sign step.

**Debug dumps** (`~/.rigel/debug/`)
`enroll_N_raw.wav` / `enroll_N_trimmed.wav` from the last enrollment and
the last 12 `utt_<ms>_{speech|nospeech}.wav` utterances the listener
captured — the ground truth for "what did it actually hear".

---

## Dev & Build Terms

**Vite**
The dev server/bundler for the React front end. `npm run dev` serves it at
`http://localhost:1425`; `npx tauri dev` wraps it in the native Tauri
shell.

**`RIGEL_PORT`**
Environment variable overriding the sidecar's listen port (default
`5140`).

**`RIGEL_DB`**
Environment variable overriding the SQLite database path (default
`~/.rigel/rigel.db`); used by tests to point at a temp file.

**Re-sign** (`codesign --force --deep -s - --identifier com.tonyseneadza.rigel`)
The step after every `tauri build` that gives the ad-hoc-signed bundle a
stable identifier so macOS keeps the microphone grant (see **TCC**).

**`cmake`**
Build-time requirement added by `whisper-rs`, which compiles whisper.cpp
into the native shell.

**`.venv`**
The Python virtual environment the sidecar runs from (`./.venv/bin/python
-m sidecar`), created per the Quick Start in the main README.

---

## See Also

- [`docs/FILE-REFERENCE.md`](FILE-REFERENCE.md) — every tracked file in the
  repo, what it's for, and what its extension means
- [`docs/README.md`](README.md) — documentation index and templates
- [`docs/QUICK-REFERENCE.md`](QUICK-REFERENCE.md) — which template to use
  for new docs
- [`../README.md`](../README.md) — project overview, architecture diagram,
  quick start
