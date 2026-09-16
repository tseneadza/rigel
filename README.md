# RIGEL 🌌

### Really Intelligent Graphical Execution Layer

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)
[![Status: early](https://img.shields.io/badge/status-early--slice-38bdf8.svg)](#-project-status)

**Rigel** is a voice-activated, autonomous desktop agent designed to eliminate the friction of manual operating system navigation. Inspired by the fictional JARVIS AI system, Rigel combines a futuristic, holographic-style HUD visual interface with a powerful local execution engine.

Instead of clicking through nested folders and menus, you look to your navigational anchor—**Rigel**—to instantly open applications, manage file structures, and execute local tasks entirely through natural language prompts.

---

## 🕶️ The Aesthetic & Concept

* **The Navigational Anchor:** Named after the luminous blue supergiant star in the Orion constellation, Rigel acts as your bright guiding anchor through the massive ocean of your local computer files.
* **The Blazing Blue HUD:** A high-contrast, glowing ice-blue interface. The central orb — a white-hot nucleus wrapped in layered glow, expanding ripple rings, and electrons streaking along tilted 3D orbits — breathes like a distant star when idle and spins up when it's working.

---

## 🚦 Project Status

Rigel is in its **first slice**. What works today:

* ✅ **Full-screen scalable orb** (Tauri + React) — the "blazing blue" presence, live and animating as a 3D Bohr-style atom: electrons on three tilted orbits pass behind the nucleus and re-emerge.
* ✅ **Resizable, pinnable orb** — a size slider (60–620 px) and corner picker in the console let you shrink the orb into a corner; the choice persists across launches in a `settings` table.
* ✅ **Text conversation loop** — talk to Rigel by typing; the transcript rehydrates from Rigel's own store on launch.
* ✅ **Logging from day one** — every conversation turn *and* every command Rigel attempts is written to a local SQLite store (`~/.rigel/rigel.db`).
* ✅ **Pluggable LLM brain** — pick **Claude** or a **local Ollama** model from Settings (⚙ → Brain). Ollama options are live-probed against this machine's RAM so you don't pick a model that will thrash. Falls back to the original regex stub if the chosen provider is unreachable. See [`docs/features/llm-brain.md`](docs/features/llm-brain.md).
* ✅ **Auto-shrink while working** — the moment Rigel starts thinking, the header and full chat console disappear and the actual OS window (not just the CSS orb) shrinks down to a small borderless square holding *only* the orb — no title bar, no text input, nothing else — then restores its exact prior size/position and the full console once the reply lands.
* ✅ **Deep-space look** — a solid black background with a scattered starfield and a soft nebula glow behind the orb; never transparent to the desktop.

Deferred to later slices (scaffolded, not yet wired):

* 🔜 **Voice I/O** — Rigel will get its own fresh STT/TTS pipeline.
* 🔜 **Real command execution** — the OS-hook layer (open/close apps, file CRUD) runs behind approval gates. For now Rigel *detects and logs* command intents (now via a real LLM, still without executing them).
* 🔜 **Hotkey-summoned input** — while the orb is shrunk to just itself, a global hotkey (not yet implemented) will be the way to bring the text input back rather than any click affordance on the orb.

---

## 🛠️ Architecture Overview

Rigel is a standalone **Tauri (Rust) + React** desktop app talking to a lean local **Python (FastAPI) sidecar**, which owns Rigel's private log/memory store. It reuses the visual and structural patterns of the OSA orb but shares no runtime or database with it.

```text
                    [ USER PROMPT (text · voice later) ]
                                   │
                                   ▼
┌───────────────────────────────────────────────────────┐
│   Rigel Desktop  —  Tauri shell + React orb (port 1425) │
└───────────────────────────┬───────────────────────────┘
                            │  HTTP  /api/rigel/*
                            ▼
┌───────────────────────────────────────────────────────┐
│   Rigel Sidecar  —  FastAPI  (port 5140)                │
│     • brain.py   → reply + command-intent parsing        │
│     • db.py      → SQLite log/memory + settings store    │
└───────────────┬───────────────────────┬───────────────┘
                ▼                       ▼
     ┌───────────────────────┐   ┌───────────────────────┐
     │  Conversation log     │   │  Command-attempt log  │
     │  (every turn)         │   │  (every intent)       │
     └───────────────────────┘   └───────────────────────┘
                        ~/.rigel/rigel.db
```

---

## 🧰 Quick Start

### Prerequisites
* **Node.js 18+** and npm
* **Rust** (stable) + the [Tauri 2 prerequisites](https://v2.tauri.app/start/prerequisites/) for your OS
* **Python 3.11+**
* Supported platforms: macOS / Windows 11 / Linux (X11/Wayland)
* Optional, only if you want a real LLM brain instead of the default stub:
  an [Anthropic API key](https://console.anthropic.com/) and/or a local
  [Ollama](https://ollama.com) install — see step 4 below.

### 1. Clone
```bash
git clone https://github.com/tseneadza/rigel.git
cd rigel
```

### 2. Start the sidecar (terminal 1)
Run this from the **repo root** — `sidecar` is a package, so `python -m sidecar` won't resolve from inside the folder.
```bash
python3 -m venv .venv
./.venv/bin/pip install -r sidecar/requirements.txt
./.venv/bin/python -m sidecar          # serves http://127.0.0.1:5140
```

### 3. Start the desktop app (terminal 2)
```bash
cd desktop
npm install
npm run dev            # web preview at http://localhost:1425
# — or, for the native window —
npx tauri dev          # compiles the Tauri shell (first run is slow)
```
If Vite complains that port 1425 is in use, a previous dev server is still running: `lsof -ti:1425 | xargs kill -9`.

The orb appears on launch. Type to Rigel; every turn and every detected command lands in `~/.rigel/rigel.db`.

### 4. (Optional) Choose an LLM brain
By default Rigel replies with a simple pattern-matching stub — no setup
required. To have it reply through a real LLM instead, open Settings (⚙,
top-right) → **Brain** tab and pick:
* **Claude** — set `export ANTHROPIC_API_KEY=sk-ant-...` in the shell you
  launch the sidecar from, then pick a model in Settings.
* **Ollama (local)** — [install Ollama](https://ollama.com), pull a model
  (`ollama pull llama3.2:3b`), then pick it in Settings — it's live-probed
  against your machine's actual RAM so you can see which models will
  actually run responsively.

Full walkthrough (including a couple of environment gotchas worth knowing
about): [`docs/setup/llm-brain.md`](docs/setup/llm-brain.md).

---

## 🗣️ Interactive Syntax Examples

Once the orb is up, talk to Rigel (voice arrives in a later slice):

> **User:** *"Rigel, open VS Code and Chrome side-by-side."*
>
> **Rigel:** *"Understood. I would open app — but command execution is not wired up yet, so I've logged the intent instead. What's next?"*

Inspect what Rigel has logged at any time:
```bash
curl http://127.0.0.1:5140/api/rigel/logs | python3 -m json.tool
```

---

## 🗂️ Repository Layout

```
rigel/
├── desktop/          Tauri + React front end (the orb & console)
│   ├── src/          React components (RigelOrb, ChatConsole, SettingsPanel, ResizeControl, App)
│   └── src-tauri/    Rust/Tauri native shell
└── sidecar/          Python FastAPI service
    ├── app.py            routes: /chat /state /logs /health /settings/*
    ├── brain.py          reply + command-intent dispatch (stub or LLM)
    ├── llm_providers.py  Claude + Ollama backends, hardware/availability probing
    └── db.py             SQLite store: turns, command_attempts, settings
```

---

## 🤝 Contributing

Contributions to Rigel are welcome — whether you're building the voice pipeline, wiring the OS-hook execution layer behind approval gates, dropping a real LLM into `brain.py`, or refining the HUD. Fork the repo and open a Pull Request.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
