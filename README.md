# RIGEL 🌌

### Responsive Interface for Graphical Execution & Logistics

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

**Rigel** is a voice-activated, autonomous desktop agent designed to eliminate the friction of manual operating system navigation. Inspired by the fictional JARVIS AI system, Rigel combines a futuristic, holographic-style HUD visual interface with a powerful local execution engine.

Instead of clicking through nested folders and menus, you look to your navigational anchor—**Rigel**—to instantly open applications, manage file structures, and execute local tasks entirely through natural language voice prompts.

---

## 🕶️ The Aesthetic & Concept

* **The Navigational Anchor:** Named after the luminous blue supergiant star in the Orion constellation, Rigel acts as your bright guiding anchor through the massive ocean of your local computer files.
* **The Blazing Blue HUD:** Features a high-contrast, glowing ice-blue visual interface. The central voice visualizer pulses like a distant star when idle and bursts into life upon hearing its wake word.

---

## ⚡ Core Features

* **🎙️ Voice-First Operating Layer:** Deep voice-recognition model optimized to catch its wake word (*"Rigel"*) even over background microphone noise.
* **📁 Total File Manipulation:** Create, save, edit, read, and delete application files across your local hard drives purely via voice commands.
* **⚙️ App Orchestration:** Launch, close, and tile applications simultaneously to instantly spin up customized developer or creative workspaces.
* **🚀 Maximum Velocity Execution:** Uses direct system hooks to route tasks bypass standard GUI bottlenecks, executing your intentions at the "speed of sound."

---

## 🛠️ Architecture Overview

Rigel runs quietly as a local background daemon, bridging natural language processing directly with low-level OS utilities.

```text
                    [ USER VOICE PROMPT ]
                             │
                             ▼
┌───────────────────────────────────────────────┐
│         Rigel Voice Core (Wake Word)            │
└───────────────────────┬─────────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│        LLM Intent Parser & Router Engine        │
└───────────────────────┬─────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
┌───────────────────────┐   ┌───────────────────────┐
│   File System Manager  │   │   OS Application Hook  │
│     (CRUD Actions)     │   │   (Open/Close/Focus)   │
└───────────────────────┘   └───────────────────────┘
```

---

## 🚦 Quick Start

### Prerequisites
* Supported Platforms: Windows 11 / macOS Sequoia / Linux (X11/Wayland)
* Python 3.11+
* Active microphone input

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/tseneadza/rigel.git
   cd rigel
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Initialize the core model and calibrate your microphone:
   ```bash
   python rigel.py --setup
   ```

4. Boot up the HUD interface:
   ```bash
   python rigel.py --boot
   ```

---

## 🗣️ Interactive Syntax Examples

Once the HUD initializes and displays the glowing blue anchor ring, trigger the agent using its wake word:

> **User:** *"Rigel, initialize workspace."*
>
> **Rigel:** *(Visualizer spins rapidly)* `"System localized, sir. All core applications are online and files are synched. What is our next objective?"`

### Application Control
* *"Rigel, open VS Code and Chrome side-by-side."*
* *"Rigel, terminate all background creative apps."*

### File Management
* *"Rigel, create a new markdown file in my Documents folder named project_notes."*
* *"Rigel, append the text 'Review structural code tonight' to my active todo list."*
* *"Rigel, delete the temporary log files from yesterday morning."*

---

## 🤝 Contributing

Contributions to Rigel are welcome! Whether you are optimizing the voice recognition pipeline, adding support for new operating system hooks, or refining the glowing HUD UI animations, please feel free to fork the repo and submit a Pull Request.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
