# RIGEL 🌌

### Responsive Interface for Graphical Execution & Logistics

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)
[![Status: early](https://img.shields.io/badge/status-early--slice-38bdf8.svg)](#-project-status)

**Rigel** is a voice-activated, autonomous desktop agent designed to eliminate the friction of manual operating system navigation. Inspired by the fictional JARVIS AI system, Rigel combines a futuristic, holographic-style HUD visual interface with a powerful local execution engine.

Instead of clicking through nested folders and menus, you look to your navigational anchor—**Rigel**—to instantly open applications, manage file structures, and execute local tasks entirely through natural language prompts.

---

## 🕶️ The Aesthetic & Concept

* **The Navigational Anchor:** Named after the luminous blue supergiant star in the Orion constellation, Rigel acts as your bright guiding anchor through the massive ocean of your local computer files.
* **The Blazing Blue HUD:** A high-contrast, glowing ice-blue interface. The central orb — a white-hot core wrapped in layered glow, expanding ripple rings, and orbiting satellites — breathes like a distant star when idle and spins up when it's working.

---

## 🚦 Project Status

Rigel is in its **first slice**. What works today:

* ✅ **Full-screen scalable orb** (Tauri + React) — the "blazing blue" presence, live and animating.
* ✅ **Text conversation loop** — talk to Rigel by typing; the transcript rehydrates from Rigel's own store on launch.
* ✅ **Logging from day one** — every conversation turn *and* every command Rigel attempts is written to a local SQLite store (`~/.rigel/rigel.db`).

Deferred to later slices (scaffolded, not yet wired):

* 🔜 **Voice I/O** — Rigel will get its own fresh STT/TTS pipeline.
* 🔜 **Real command execution** — the OS-hook layer (open/close apps, file CRUD) runs behind approval gates. For now Rigel *detects and logs* command intents without executing them.
* 🔜 **LLM brain** — the intent parser is a pluggable stub (`sidecar/brain.py`) with a clean seam for dropping in Claude.

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
│     • db.py      → SQLite log/memory store               │
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

### 1. Clone
```bash
git clone https://github.com/tseneadza/rigel.git
cd rigel
```

### 2. Start the sidecar (terminal 1)
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
npm run tauri dev      # compiles the Tauri shell (first run is slow)
```

The orb appears on launch. Type to Rigel; every turn and every detected command lands in `~/.rigel/rigel.db`.

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
│   ├── src/          React components (RigelOrb, ChatConsole, App)
│   └── src-tauri/    Rust/Tauri native shell
└── sidecar/          Python FastAPI service
    ├── app.py        routes: /chat /state /logs /health
    ├── brain.py      reply + command-intent parser (LLM seam)
    └── db.py         SQLite log/memory store
```

---

## 🤝 Contributing

Contributions to Rigel are welcome — whether you're building the voice pipeline, wiring the OS-hook execution layer behind approval gates, dropping a real LLM into `brain.py`, or refining the HUD. Fork the repo and open a Pull Request.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
