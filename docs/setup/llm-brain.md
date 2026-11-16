# Setup Guide: LLM Brain (Claude / Ollama)

## Overview
Rigel's brain defaults to a regex stub. This guide walks through switching
it to a real LLM — either **Claude** (cloud) or a **local Ollama** model —
via Settings (⚙ → Brain). Assumes you've already completed the main
[Quick Start](../../README.md#-quick-start) (sidecar + desktop running).

## Prerequisites

### For Claude
- An Anthropic API key, saved in your macOS login Keychain as
  `rigel-anthropic-key` (Step 2).
- **Check for a stray `ANTHROPIC_BASE_URL`** in the shell that launches the
  sidecar — if it's set (e.g. by another local tool), `anthropic.
  Anthropic()` will silently route Claude calls there instead of the real
  API:
  ```bash
  echo "$ANTHROPIC_BASE_URL"   # should be empty unless you intend to proxy
  ```
  If it's set and you don't want it applied to Rigel, either unset it in
  the shell you launch the sidecar from, or launch with it cleared for
  just that process:
  ```bash
  env -u ANTHROPIC_BASE_URL ./.venv/bin/python -m sidecar
  ```

### For Ollama
- [Ollama](https://ollama.com) installed and running (`ollama serve`, or
  the menu-bar app).
- At least one model pulled: `ollama pull llama3.2:3b` is a good default
  for most machines (~2GB).
- **RAM matters** — Settings shows a fit estimate (✅/⚠/❌) for each of
  your installed models against this machine's actual RAM, live-probed via
  `psutil` + Ollama's own `/api/tags`. Don't pick a ❌ model and expect it
  to be responsive.

## Step-by-Step Setup

### Step 1: Install the new sidecar dependencies
**Goal:** get `anthropic` and `psutil` into the venv (already done if
you've pulled this change and reinstalled requirements).
```bash
cd rigel
./.venv/bin/pip install -r sidecar/requirements.txt
```
**Verification:**
```bash
./.venv/bin/python -c "import anthropic, psutil; print('ok')"
```

### Step 2 (Claude only): save your key in the Keychain
Copy the key to the clipboard, then run this. It stores the key without it
appearing on screen, in your shell history or in `ps`:
```bash
k=$(pbpaste); printf 'add-generic-password -U -s rigel-anthropic-key -a "$USER" -w "%s"\n' "$k" | security -i; unset k
```
Or use **Keychain Access → File → New Password Item** with *Keychain Item
Name* `rigel-anthropic-key`. Restart the sidecar afterwards; it caches the key
after the first read (`sidecar/keychain.py`).

Check it (prints only where the key came from, never the key):
```bash
curl -s 127.0.0.1:5140/api/rigel/settings/llm-options | grep -o '"api_key_source":[^,}]*'
# "api_key_source":"keychain"
```

**Fallback:** if there's no Keychain item (off-Mac, or a one-off override),
Rigel uses `ANTHROPIC_API_KEY` from the environment of the shell that
launched the sidecar.

### Step 3 (Ollama only, if a custom port/host): point Rigel at it
Rigel defaults to `http://localhost:11434` (Ollama's stock port), but
auto-detects a non-default setup from your environment:
```bash
# Either of these, if your Ollama is bound elsewhere:
export OLLAMA_API_URL=http://localhost:12434     # takes priority if set
export OLLAMA_HOST=0.0.0.0:12434                  # else derived from this

# Optional — keeps the model loaded between chat turns for responsiveness:
export OLLAMA_KEEP_ALIVE=2h
```

### Step 4: (re)start the sidecar
```bash
./.venv/bin/python -m sidecar
```
**Expected Output:**
```
INFO:     Uvicorn running on http://127.0.0.1:5140
```

### Step 5: pick the brain in Settings
1. Open the desktop app, click the ⚙ gear icon (top-right).
2. Go to the **Brain** tab.
3. Choose **Claude** (pick a model; a status line shows whether your API
   key is configured) or **Ollama** (pick from your live-probed installed
   models).
4. Click **Save**.

## Configuration Reference
```bash
# Claude
# Key: Keychain item `rigel-anthropic-key` (see Step 2). Env vars are fallbacks.
RIGEL_KEYCHAIN_SERVICE=rigel-anthropic-key  # optional: use a different Keychain item
ANTHROPIC_API_KEY=sk-ant-...       # fallback only, if no Keychain item
ANTHROPIC_BASE_URL=                # leave unset unless you intend a proxy

# Ollama (all optional — auto-detected/derived if unset)
OLLAMA_API_URL=http://localhost:12434
OLLAMA_HOST=0.0.0.0:12434
OLLAMA_KEEP_ALIVE=2h
```

## Verification

### Health Check Checklist
- [ ] `GET /api/rigel/settings/llm-options` reflects reality:
  ```bash
  curl http://127.0.0.1:5140/api/rigel/settings/llm-options | python3 -m json.tool
  ```
  Expected: `claude.api_key_configured: true` if you exported a key in
  this shell; `ollama.installed: true` with your real pulled models if
  Ollama is running.
- [ ] Settings → Brain tab shows the same data in the UI.
- [ ] A chat message produces a reply that **isn't** the canned stub text
  ("Understood. I would ... — but command execution is not wired up
  yet...") — if you see that exact string with your provider selected,
  the call failed and fell back; check the sidecar's console output for a
  `"... brain failed (...); falling back to stub."` warning.

### Testing Commands
```bash
curl -X POST http://127.0.0.1:5140/api/rigel/settings/llm-config \
  -H "Content-Type: application/json" \
  -d '{"provider": "ollama", "ollama_model": "llama3.2:3b"}'

curl -X POST http://127.0.0.1:5140/api/rigel/chat \
  -H "Content-Type: application/json" \
  -d '{"text": "Hey Rigel, open Chrome"}'
```

## Troubleshooting
See [`docs/troubleshooting/llm-brain.md`](../troubleshooting/llm-brain.md)
for the ANTHROPIC_BASE_URL redirect gotcha, "model not found" errors,
Ollama not detected, and the silent-fallback-to-stub symptom.

## Next Steps
- [Feature doc](../features/llm-brain.md) — full technical detail.
- [Architecture doc](../architecture/llm-provider-selection.md) — why it's
  built this way.
- [API reference](../api/llm-settings-endpoints.md) — the three endpoints.
