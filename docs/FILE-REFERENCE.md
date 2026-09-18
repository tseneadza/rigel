# File Reference

Every tracked file in the repo, what it's for, and what its extension
means. Companion to [`GLOSSARY.md`](GLOSSARY.md) (which covers vocabulary)
— this doc covers the filesystem itself. Build/dependency output
(`node_modules/`, `dist/`, `target/`, `__pycache__/`, `.venv/`) is excluded
since it's generated, not authored — see [`.gitignore`](../.gitignore) for
the full exclusion list.

---

## File Extensions

| Extension | Format / Language | Meaning in this repo |
|-----------|-------------------|------------------------|
| `.jsx` | JavaScript + JSX | A React component — JS with inline HTML-like markup. Compiled by Vite/Babel; browsers never run it directly. |
| `.js` | JavaScript (ES module) | Plain JS logic with no markup — API clients, small platform-integration modules. `desktop/package.json` sets `"type": "module"`, so these use `import`/`export`. |
| `.css` | Cascading Style Sheets | Visual styling. Rigel uses one hand-written global stylesheet, no CSS framework or preprocessor. |
| `.html` | HTML | A page shell. `desktop/index.html` is the single entry point Vite injects the built JS bundle into. |
| `.py` | Python | The sidecar's source — FastAPI routes, the brain, the DB layer, LLM providers. |
| `.rs` | Rust | Tauri's native shell — the actual OS process that opens the window and exposes system APIs to the webview. |
| `.toml` | TOML (Tom's Obvious Minimal Language) | Rust's package-manifest format — `Cargo.toml` declares the Tauri crate's name, dependencies, and build target. |
| `.json` | JSON | Structured config and data with no comments allowed — `package.json` (npm), `tauri.conf.json` (Tauri), `capabilities/default.json` (Tauri permissions), `app.json` (this app's own metadata). |
| `.md` | Markdown | Prose documentation — everything under `docs/`, plus `README.md` and this file. Rendered by GitHub, editors, and most doc tooling directly from plain text. |
| `.txt` | Plain text | `requirements.txt` — pip's plain, line-per-package dependency list (no JSON/TOML structure needed for its simple `name>=version` syntax). |
| `.icns` | Apple Icon Image | macOS's native multi-resolution app-icon container — used for the `.app` bundle and `.dmg` installer. |
| `.ico` | Windows Icon | Windows' native multi-resolution icon container — used for the `.exe`'s taskbar/title-bar icon. |
| `.png` | Portable Network Graphics | Individual raster icon sizes (e.g. `32x32.png`, `Square150x150Logo.png`) — source images Tauri's bundler packs into the platform-specific `.icns`/`.ico` containers, plus Windows Store tile assets. |
| `.plist` | Apple property list (XML) | `desktop/src-tauri/Info.plist` — extra keys merged into the app bundle's `Info.plist`; here `NSMicrophoneUsageDescription`, the text macOS shows when asking for microphone access. |
| `.lock` | Cargo lockfile (TOML) | `Cargo.lock` — Rust's exact resolved dependency tree, the equivalent of `package-lock.json`. Committed so the audio/whisper dependency chain (which needs `half` pinned) reproduces exactly. |
| `.gitignore` (no extension) | Git ignore rules | Tells Git which generated/local files to never track (there are two: one repo-wide, one scoped to `desktop/src-tauri/` for Rust-specific build output). |
| *(none)* — `LICENSE` | Plain text | The project's license text; conventionally left without an extension. |

---

## Root

| File | Purpose |
|------|---------|
| [`README.md`](../README.md) | Project overview: what Rigel is, current status, architecture diagram, quick start, repo layout. |
| [`LICENSE`](../LICENSE) | MIT license text. |
| [`app.json`](../app.json) | Rigel's own app manifest — id, description, and how a host tool (e.g. AgenticOS) would start Rigel's web (`sidecar`) and desktop (`Tauri`) halves. Not consumed by Rigel itself at runtime. |
| [`.gitignore`](../.gitignore) | Repo-wide ignore rules: Python/Node/Rust build output, the user's `.rigel/` runtime store, secrets, editor/OS cruft, logs. |

## `desktop/` — Tauri + React front end

| File | Purpose |
|------|---------|
| [`package.json`](../desktop/package.json) | npm manifest: scripts (`dev`, `build`, `preview`, `tauri`) and dependencies — React 19, the Tauri JS API/CLI, the global-shortcut plugin, Vite. |
| `package-lock.json` | npm's exact, resolved dependency tree — ensures every install reproduces the same versions. Not hand-edited. |
| [`vite.config.js`](../desktop/vite.config.js) | Vite dev-server/build config: fixed port `1425` (chosen to avoid clashing with AgenticOS's own Vite server on `1420`), Tauri-specific HMR host/port handling, and watch exclusions. |
| [`index.html`](../desktop/index.html) | The single HTML page Vite serves and bundles into. Contains only a `#root` mount point and the script tag loading `src/main.jsx`. |

### `desktop/src/` — application code

| File | Purpose |
|------|---------|
| [`main.jsx`](../desktop/src/main.jsx) | Entry point: mounts `<App />` into `#root` and imports the global stylesheet. |
| [`App.jsx`](../desktop/src/App.jsx) | Root component — owns top-level state (transcript, orb state, online status, `manualMinimize`), derives `minimized` (with the 2.5 s auto-minimize delay), wires the hotkey and native-window-sync effects, subscribes to the native voice events (transcript → chat → spoken reply), and lays out header/orb/console/settings. |
| [`api.js`](../desktop/src/api.js) | Thin `fetch` wrapper for every sidecar endpoint (`/state`, `/logs`, `/chat`, orb/LLM/voice settings). Base URL overridable via `VITE_RIGEL_API`. |
| [`voice.js`](../desktop/src/voice.js) | Wrappers for every native voice command (`speak`, `enrollWakeword`, `downloadSttModel`, `setVoiceEnabled`, …) and `voice://…` event (`onTranscript`, `onVoiceState`, …); `subscribeInEffect` (leak-safe Tauri event subscription for React effects) and `looksLikeSpeech` (rejects whisper's `[BLANK_AUDIO]`-style output). No-ops outside a Tauri webview. |
| [`hotkey.js`](../desktop/src/hotkey.js) | Registers the global `Cmd/Ctrl+Shift+R` toggle — real OS-level shortcut in Tauri, `keydown`-listener fallback in a plain browser. |
| [`nativeWindow.js`](../desktop/src/nativeWindow.js) | Resizes/repositions the *actual* OS window (`shrinkToCorner` / `restoreRestingBounds`) and toggles its drop shadow off while minimized — a no-op outside a Tauri webview. |
| [`styles.css`](../desktop/src/styles.css) | The single global stylesheet: CSS custom properties for the palette, the starfield/nebula background, and every component's layout and animation. |

### `desktop/src/components/`

| File | Purpose |
|------|---------|
| [`RigelOrb.jsx`](../desktop/src/components/RigelOrb.jsx) | The orb itself — nucleus, glow, ripple rings, orbiting electrons — plus drag-to-reposition handling. |
| [`ChatConsole.jsx`](../desktop/src/components/ChatConsole.jsx) | Text input + scrolling transcript; posts each message to the sidecar via `api.js`. |
| [`SettingsPanel.jsx`](../desktop/src/components/SettingsPanel.jsx) | Modal with three tabs — Orb (delegates to `ResizeControl`), Brain (LLM provider/model picker, backed by `/settings/llm-*`) and Voice (wake-word enrollment, speech-model download, listen toggle, TTS voice picker, backed by `/settings/voice-config` and the native voice commands). |
| [`ResizeControl.jsx`](../desktop/src/components/ResizeControl.jsx) | Orb size slider + corner picker, used inside the Settings panel's Orb tab. |

### `desktop/src-tauri/` — the native Rust shell

| File | Purpose |
|------|---------|
| [`Cargo.toml`](../desktop/src-tauri/Cargo.toml) | Rust package manifest — crate name/type, and dependencies (`tauri`, `tauri-plugin-log`, `tauri-plugin-global-shortcut`, `serde`/`serde_json`, and for voice: `cpal`, `hound`, `rustpotter`, `whisper-rs`, with `half` pinned — see the comment there). Rust's equivalent of `package.json`. |
| `Cargo.lock` | Exact resolved Rust dependency tree; not hand-edited. |
| [`Info.plist`](../desktop/src-tauri/Info.plist) | Extra bundle keys Tauri merges into the app's `Info.plist` — the microphone usage description macOS shows on first mic access. |
| [`build.rs`](../desktop/src-tauri/build.rs) | Cargo build script, runs before compilation — here it just invokes `tauri_build::build()` to generate Tauri's own codegen (icons, config embedding, etc.). |
| [`tauri.conf.json`](../desktop/src-tauri/tauri.conf.json) | Tauri's main config: window chrome (borderless — `decorations: false`, size, `transparent: true` + `macOSPrivateApi` so the minimized orb has no background; the full-size starfield is CSS), dev-server URL, build commands, bundle icon set. |
| [`.gitignore`](../desktop/src-tauri/.gitignore) | Rust-specific ignores — `/target/` (compiled output) and `/gen/schemas` (Tauri-generated permission schemas). |
| [`src/main.rs`](../desktop/src-tauri/src/main.rs) | Binary entry point — just calls into `app_lib::run()`. The `windows_subsystem` attribute suppresses a console window on Windows release builds. |
| [`src/lib.rs`](../desktop/src-tauri/src/lib.rs) | The actual Tauri app setup: registers the global-shortcut plugin, the voice commands and managed state, file logging (20 MB × 3, release builds included, at `~/Library/Logs/com.tonyseneadza.rigel/`), and starts the Tauri runtime. |
| [`src/voice/mod.rs`](../desktop/src-tauri/src/voice/mod.rs) | Voice module root: `voice_set_enabled`/`voice_is_enabled` commands, the listener handle, and the **speech gate** that makes the wake-word listener deaf while Rigel speaks. |
| [`src/voice/listener.rs`](../desktop/src-tauri/src/voice/listener.rs) | The always-on listening thread: mic → rustpotter wake-word detection → adaptive-RMS command recording → whisper transcription; emits `voice://state`/`transcript`/`error`, logs detection scores, dumps captured audio to `~/.rigel/debug/`. |
| [`src/voice/enroll.rs`](../desktop/src-tauri/src/voice/enroll.rs) | Wake-word enrollment: three timed recordings, `trim_to_speech` (endpointing rustpotter lacks), builds and saves `~/.rigel/wakeword.rpw`. Includes unit tests and an ignored real-audio test. |
| [`src/voice/stt.rs`](../desktop/src-tauri/src/voice/stt.rs) | Speech-to-text: downloads `ggml-base.en.bin` via `curl`, caches the whisper context, transcribes (mono/16 kHz conversion, non-speech tokens suppressed), rejects `[BLANK_AUDIO]`-style output. |
| [`src/voice/tts.rs`](../desktop/src-tauri/src/voice/tts.rs) | Text-to-speech via `/usr/bin/say`: `voice_speak`/`voice_stop_speaking`/`voice_list_tts_voices`; tracks the child process, emits `speaking`/`idle`, drives the speech gate. |
| [`src/voice/capture.rs`](../desktop/src-tauri/src/voice/capture.rs) | `record_seconds()` — blocking one-shot mic capture used by enrollment. |
| [`capabilities/default.json`](../desktop/src-tauri/capabilities/default.json) | Tauri's permission manifest for the `main` window — explicitly allow-lists window resize/reposition, global-shortcut register/unregister, and `core:event:default` (without which JS `listen()` silently receives no `voice://…` events), per Tauri 2's capability-based security model (nothing is allowed by default). |

### `desktop/src-tauri/icons/`

All raster/container icon assets the bundler packs into each platform's
installer and app package: numbered `.png` sizes (`32x32.png` up to
`128x128@2x.png`) and `Square*Logo.png`/`StoreLogo.png` for Windows Store
tiles, plus the platform-native containers `icon.icns` (macOS) and
`icon.ico` (Windows), and `android/` / `ios/` sets generated by
`tauri icon` (unused today, kept so a mobile target needs no re-run).
Referenced from the `bundle.icon` list in `tauri.conf.json`.

## `sidecar/` — Python FastAPI service

| File | Purpose |
|------|---------|
| [`__init__.py`](../sidecar/__init__.py) | Makes `sidecar/` an importable Python package; its docstring states the module's scope (standalone, own SQLite store, forked in spirit from AgenticOS's sidecar). |
| [`__main__.py`](../sidecar/__main__.py) | Lets the package run as a script: `python -m sidecar` calls `app.main()`, which starts the `uvicorn` server. |
| [`app.py`](../sidecar/app.py) | FastAPI app: every `/api/rigel/*` route (`chat`, `state`, `logs`, `health`, orb/LLM/voice settings), request/response models, and validation. |
| [`brain.py`](../sidecar/brain.py) | Turns user text into `(reply, commands)` — dispatches to a configured LLM provider or the regex stub. |
| [`db.py`](../sidecar/db.py) | SQLite layer: connection/migration, and read/write functions for the `turns`, `command_attempts`, and `settings` tables. |
| [`llm_providers.py`](../sidecar/llm_providers.py) | Claude and Ollama backends, plus hardware/availability probing (`probe_ollama`, `claude_api_key_configured`) for the Settings UI. |
| [`requirements.txt`](../sidecar/requirements.txt) | Pinned minimum versions for `fastapi`, `uvicorn`, `anthropic`, `psutil` — installed into `.venv` per the README's Quick Start. |

## `docs/`

| File | Purpose |
|------|---------|
| [`README.md`](README.md) | Documentation index: where real (non-template) docs live, quick navigation by audience, and how to use the templates below. |
| [`QUICK-REFERENCE.md`](QUICK-REFERENCE.md) | Decision tree + copy-paste snippets for picking the right template fast. |
| [`GLOSSARY.md`](GLOSSARY.md) | Vocabulary reference — product concepts, architecture components, data model, desktop/window terms. |
| `FILE-REFERENCE.md` | This file. |
| `TEMPLATE-*.md` (8 files) | Blank-slate templates for API endpoint, architecture, command-intent, component, database-schema, feature, setup-guide, and troubleshooting docs — copied and filled in per `docs/README.md`'s instructions, never edited in place. |
| `api/`, `architecture/`, `features/`, `setup/`, `troubleshooting/` | Filled-in docs for shipped features (currently: the LLM brain, orb minimize/expand, the voice pipeline), organized by the same categories as the templates above. |

---

## See Also

- [`GLOSSARY.md`](GLOSSARY.md) — terminology used across these files
- [`README.md`](README.md) — documentation index and templates
- [`../README.md`](../README.md) — project overview and repo layout diagram
