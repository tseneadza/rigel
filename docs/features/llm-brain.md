# Feature: Pluggable LLM Brain (Claude / Ollama)

## Overview
Rigel's brain (`sidecar/brain.py`) started as a regex stub that detects a
handful of command intents and returns a canned reply. This feature makes
the brain pluggable from the Settings window: pick **Claude** (cloud) or a
**local Ollama** model, and Rigel routes every chat turn through that model
instead of the stub. It's the "drop in a real LLM" seam the original stub's
docstring described, now wired up end to end — including for a fully local,
no-API-key setup via Ollama.

## Status
- [ ] Planned
- [x] In Development
- [ ] Alpha/Beta
- [ ] Production

## User-Facing Description
Click the ⚙ gear icon (top-right of the Rigel window) to open **Settings**.
The **Brain** tab lets you choose:
- **Basic** — the original pattern-matching stub (default, no setup).
- **Claude** — pick from the current Claude model tiers (Opus 5 / Sonnet 5 /
  Haiku 4.5). Requires `ANTHROPIC_API_KEY` to be set in the environment the
  sidecar runs in; Settings shows whether it's currently configured.
- **Ollama (local)** — Settings live-probes your local Ollama install,
  showing every model you've already pulled with its size and a
  responsiveness estimate for *this* machine (✅ fits comfortably / ⚠ may
  run slowly / ❌ not recommended), based on your detected system RAM.

Whichever provider is selected, chat behaves the same from the user's
perspective — command intents are still only detected and logged, never
executed (that's a separate, still-deferred slice).

## Technical Implementation

### Architecture
```
Settings (Brain tab) ──save──▶ POST /settings/llm-config ──▶ settings table
Settings (Brain tab) ◀─probe── GET  /settings/llm-options ──▶ live Claude/Ollama probe

ChatConsole ──send──▶ POST /chat ──▶ brain.respond(text, llm_config)
                                        │
                         ┌──────────────┼───────────────┐
                         ▼              ▼                ▼
                    stub (regex)   claude_respond    ollama_respond
                                   (Anthropic SDK,    (local HTTP,
                                    structured JSON)   JSON mode)
                                        │                │
                                   on LLMError ───▶ falls back to stub
```

### Key Components
- **Frontend:** `desktop/src/components/SettingsPanel.jsx` (new — Orb +
  Brain tabs), `desktop/src/api.js` (new `getLlmConfig`/`saveLlmConfig`/
  `getLlmOptions`), `App.jsx` (gear button), `ChatConsole.jsx` (resize
  control moved out into Settings).
- **Backend:** `sidecar/llm_providers.py` (new — both provider
  implementations + hardware/Ollama probing), `sidecar/brain.py`
  (dispatch + fallback), `sidecar/app.py` (three new endpoints).
- **Storage:** reuses the existing generic `settings` key/value table
  (`db.py`) under the key `llm_config` — no schema migration needed.
- **APIs:** see [`docs/api/llm-settings-endpoints.md`](../api/llm-settings-endpoints.md).

### Data Flow
1. User opens Settings → Brain tab; UI fetches `llm-config` (saved choice)
   and `llm-options` (live Claude key status + live Ollama model probe).
2. User picks a provider/model and hits Save → `POST /settings/llm-config`.
3. Next chat message → `POST /chat` loads the saved `llm_config` and calls
   `brain.respond(text, llm_config)`.
4. `brain.respond` dispatches to the selected provider. Both providers ask
   the model for a single JSON object `{reply, commands}` (Claude via GA
   structured outputs `output_config.format`; Ollama via `format: "json"`
   plus an explicit schema description in the system prompt).
5. If the provider call/parse fails for any reason (no API key, Ollama
   unreachable, malformed JSON), `brain.respond` logs a warning and falls
   back to the original regex stub — chat never goes silent.
6. Reply + commands are logged exactly like the stub path (same
   `turns`/`command_attempts` tables, same `"deferred"` status).

## Configuration
```
ANTHROPIC_API_KEY=sk-ant-...       # required for the Claude provider; never
                                    # stored by Rigel — read from the
                                    # environment at call time only.

# Optional — Ollama connection, auto-detected if set:
OLLAMA_API_URL=http://localhost:12434   # takes priority if set
OLLAMA_HOST=0.0.0.0:12434                # else derived from this (0.0.0.0 → localhost)
OLLAMA_KEEP_ALIVE=2h                     # passed through per-request to keep the model warm
```
See [`docs/architecture/llm-provider-selection.md`](../architecture/llm-provider-selection.md)
for why these are read this way.

## Usage Examples

### User Perspective
```
User prompt: "Hey Rigel, please open Chrome"
Rigel response (Ollama, llama3.2): "I can help you with that, but command
execution is not wired up yet, so I've logged the intent instead."
```

### Developer Perspective
```python
from sidecar import brain

llm_config = {"provider": "ollama", "ollama_model": "llama3.2:latest",
               "ollama_host": "http://localhost:11434"}
reply, commands = brain.respond("open Chrome and Safari", llm_config)
# commands == [{"action": "open_app", "args": {...}}]  (shape is model-decided)
```

## Testing
- **Manual Testing Checklist:**
  - [x] Stub provider (`provider: "stub"`) still replies exactly as before — regression-checked.
  - [x] Ollama provider produces a real (non-canned) reply and a logged command intent.
  - [x] Claude provider with no `ANTHROPIC_API_KEY` falls back to the stub instead of a 500.
  - [x] `POST /settings/llm-config` rejects an invalid provider / missing `ollama_model` with 400.
  - [x] Settings UI: Orb tab still resizes/repositions the orb from its new location.
  - [x] Settings UI: Brain tab shows live Ollama models with correct sizes and fit labels.
  - [x] Claude provider with a real API key against the live Anthropic cloud API — confirmed a genuine reply and correctly split multi-intent commands. (Required clearing this machine's `ANTHROPIC_BASE_URL`, which was pointed at local Ollama — see the architecture doc's "Environment Gotcha" section; this is a pre-existing shell-wide override, not something Rigel should silently work around.)

## Known Limitations
- The Ollama "fit" label is a simple size-vs-RAM heuristic (comfortable
  <50%, borderline <80%), not a live capability probe — it doesn't account
  for context length, concurrent apps, or actual runtime (KV cache) memory,
  which run higher than the on-disk model size.
- Each chat turn is stateless (matches the original stub's scope) — no
  conversation history is sent to the LLM yet, so multi-turn context isn't
  preserved.
- Small local Ollama models follow the structured-output convention less
  reliably than Claude (observed: a 7B-class model sometimes dropped one
  of two intents, or left `args` empty) since Ollama's `format: "json"` is
  JSON-validity-only, not schema-enforced like Claude's `output_config`.
  `_normalize_command()` degrades gracefully (empty `args` rather than a
  crash) but can't improve a model's own instruction-following.
- A shell-wide `ANTHROPIC_BASE_URL` override (set for an unrelated purpose)
  will silently redirect Rigel's Claude calls too, since that's documented
  `anthropic` SDK behavior. Rigel doesn't try to detect or override this —
  see the architecture doc's "Environment Gotcha" section.
- The Claude API key can only be set via environment variable; there's no
  in-app credential entry (a deliberate choice, see the architecture doc).

## Future Enhancements
- Send recent conversation history to the LLM for multi-turn context.
- Wire the detected command intents into the (still separate, deferred)
  real command-execution + approval-gate layer.
- Streaming replies for lower perceived latency.

## Related Features
- Depends on the still-deferred **real command execution** slice (README
  "Deferred to later slices") — commands remain detected-and-logged only.

## References
- [`docs/architecture/llm-provider-selection.md`](../architecture/llm-provider-selection.md)
- [`docs/api/llm-settings-endpoints.md`](../api/llm-settings-endpoints.md)
- `sidecar/llm_providers.py`, `sidecar/brain.py`, `sidecar/app.py`
- `desktop/src/components/SettingsPanel.jsx`
