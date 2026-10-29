# Architecture: LLM Provider Selection (Claude / Ollama Brain)

## Purpose
Lets `sidecar/brain.py` route chat turns through a real LLM (cloud Claude or
local Ollama), chosen from Settings, instead of only the regex stub —
while keeping the "always reply, log everything" guarantee Rigel was built
with from day one.

## High-Level Diagram
This diagram is scoped to provider selection only — `brain.respond()` now
wraps this whole box with a pre-check and two post-checks that this
feature never touches (see "Scope note" below the diagram).
```
┌────────────────────┐   GET/POST llm-config   ┌────────────────────┐
│  SettingsPanel.jsx  │◀───────────────────────▶│  settings table    │
│  (Orb / Brain tabs) │   GET llm-options       │  (key: llm_config) │
└──────────┬──────────┘─────────────┐           └────────────────────┘
           │                        ▼
           │              ┌───────────────────┐
           │              │ llm_providers.py  │
           │              │  probe_ollama()   │  (live /api/tags + psutil RAM)
           │              │  claude_api_key_  │
           │              │  configured()     │
           │              └───────────────────┘
           ▼
     POST /chat ──▶ brain.respond(text, llm_config)
                          │
              ┌───────────┼────────────┐
              ▼           ▼            ▼
          stub        claude_respond  ollama_respond
        (regex)      (Anthropic SDK)  (stdlib HTTP → local Ollama)
                          │                │
                     LLMError ────────▶ fall back to stub
```

**Scope note:** `respond()` itself now does more than this diagram shows —
a pure-read "what apps are open" intercept runs *before* any of this
(`_running_apps_reply`, skips the provider entirely for a deterministic
answer); per-app handler routing (`_app_commands`) and a menu-action
fallback (`_menu_action_commands`) both run *after* whichever branch above
returns, adding commands the provider itself never detected. Both are
separate features with their own architecture docs —
[`docs/architecture/app-handlers.md`](app-handlers.md) and
[`docs/architecture/menu-actions.md`](menu-actions.md) — this doc only
covers the box in the middle: which brain answers with a reply.

## Components

### `sidecar/llm_providers.py` (new)
- **Language:** Python
- **Location:** `sidecar/llm_providers.py`
- **Purpose:** Both LLM backends + the hardware/availability probing that
  feeds the Settings UI.
- **Key Files:** single file — small enough not to split yet.
- **Dependencies:** `anthropic` (Claude SDK), `psutil` (cross-platform RAM),
  stdlib `urllib` (Ollama HTTP — no new HTTP dependency needed for two
  simple calls).
- **Public Interface:**
  - `claude_respond(text, model)` — Claude, GA structured outputs.
  - `ollama_respond(text, model, host)` — local Ollama, JSON mode.
  - `probe_ollama(host)` — live model/RAM/fit data for the UI.
  - `system_ram_gb()`, `claude_api_key_configured()` — status checks.
  - `LLMError` — the single exception type both providers raise; `brain.py`
    only needs to know about this one type.

### `sidecar/brain.py` (modified)
- **Purpose:** Dispatch + fallback. Unchanged regex stub is now
  `_stub_respond`; `respond(text, llm_config)` tries the configured
  provider first, catches `LLMError`, logs a warning, and falls back to
  `_stub_respond`. (This provider dispatch was later split into its own
  `_respond_via_provider()` helper so two unrelated features — App
  Handlers and App Menu Actions — could layer their own logic around it
  without duplicating the stub/Claude/Ollama branching three times; see
  their own architecture docs for what they each add.)

### `desktop/src/components/SettingsPanel.jsx` (new)
- **Purpose:** Single settings surface (Orb + Brain tabs) — consolidates
  what used to be an inline resize control into a proper modal, per the
  decision to give the LLM picker a real "Settings window."

## Data Flow

### Primary Flow: choosing and using a brain
```
1. User opens Settings → Brain tab
2. UI fetches current llm_config + live llm-options (Claude key status,
   Ollama models/RAM/fit)
3. User picks a provider/model, hits Save → POST /settings/llm-config
   (validated server-side, same pattern as orb-config)
4. Next chat turn: POST /chat loads llm_config, calls brain.respond()
5. brain.respond() dispatches to the provider, which asks the model for a
   single structured JSON object and parses it into (reply, commands)
6. On any provider failure, falls back to the stub — chat never goes silent
```

### Error Handling
Both providers convert every failure mode (auth, network, rate limit, bad
JSON, unreachable host, missing SDK credentials) into the single
`LLMError` type. `brain.py` only has one `except` to reason about, and logs
via the standard `logging` module rather than swallowing failures silently
— visible in the sidecar's console output for debugging.

## Concurrency & State Management
No new concurrency concerns: FastAPI handles `/chat` requests one at a
time per the existing app (no change from the stub's synchronous model).
Both provider calls are synchronous, blocking network calls — acceptable
for a first LLM slice; streaming is a noted future enhancement.

## Performance Characteristics
- Claude: typical cloud round-trip latency (network + model inference).
- Ollama: local inference — latency depends entirely on the chosen model
  size vs. this machine's hardware, which is exactly why the "fit" probing
  exists.
- `OLLAMA_KEEP_ALIVE` (when set in the environment) is passed through as a
  per-request `keep_alive` field on every Ollama call, so the model stays
  resident between chat turns instead of reloading from disk each time —
  directly relevant to "responsive on this computer."
- `probe_ollama()` uses a short (1.5s) timeout so a down/unreachable Ollama
  doesn't stall the Settings UI.

## External Dependencies
| Dependency | Version | Purpose | License |
|-----------|---------|---------|---------|
| `anthropic` | >=0.69 | Official Claude SDK — messages API, structured outputs | MIT |
| `psutil` | >=6.0 | Cross-platform total-RAM detection (no stdlib equivalent works on Windows + macOS + Linux alike) | BSD |

## Alternative Approaches Considered

- **Forced tool-calling (`tool_choice`) vs. structured outputs:** Chose GA
  `output_config: {format: {type: "json_schema", ...}}` for Claude — it's
  the documented, non-beta way to guarantee parseable JSON for a single,
  non-agentic call, and avoids assistant-prefill patterns that are
  rejected on current Claude models.

- **API key stored in Rigel's DB vs. environment variable only:** Chose
  environment-variable-only. Rigel is a local desktop app; storing a
  credential in a plaintext SQLite `settings` row adds a real exposure
  surface for no material convenience gain over `export
  ANTHROPIC_API_KEY=...`, and matches the Anthropic SDK's own recommended
  credential resolution order. Settings shows configured/not-configured
  status instead of a key-entry field.

- **Hardcoded Ollama model catalog vs. live `/api/tags` probing:** Chose
  live probing. A hardcoded list of "recommended local models" goes stale
  the moment a new model ships, and can't know what the user has actually
  pulled. `/api/tags` already reports each installed model's real on-disk
  size, which is a better signal than a guess from a static table.

- **Hard failure vs. fallback-to-stub on provider error:** Chose fallback.
  Rigel's founding requirement is "log every conversation turn and command
  intent from day one" — a provider outage shouldn't take that down. The
  fallback is logged loudly (not silent) so misconfiguration is still
  debuggable.

- **Free-form `args` object vs. a JSON-encoded `args_json` string:** Started
  with `args: {"type": "object"}` in `RESPONSE_SCHEMA`, but Claude's strict
  structured-output validator rejects any `object`-typed schema node that
  doesn't set `additionalProperties: false` — which would force `args` to
  always be `{}`, defeating the point (command args vary per action: a
  single `target`, or several named fields). Switched to `args_json`, a
  plain JSON-encoded string, which has no such constraint; `_parse_response_
  json()` decodes it back into a dict so nothing downstream (`brain.py`,
  `app.py`, the UI) ever sees the difference. Verified against the real
  Anthropic API — see "Environment gotcha" below.

## Environment Gotcha: `ANTHROPIC_BASE_URL`

During testing on this machine, `ANTHROPIC_API_KEY` was a real key, but
`ANTHROPIC_BASE_URL` was *also* set — to `http://localhost:12434`, the same
port as the local Ollama server. `anthropic.Anthropic()` correctly honors
`ANTHROPIC_BASE_URL` (that's documented SDK behavior for enterprise
proxies), so every "Claude" call on this machine was silently landing on
Ollama's API instead of Anthropic's cloud — which doesn't recognize model
IDs like `claude-sonnet-5`, producing a 404 that `brain.py` correctly
caught and fell back to the stub for.

This is **not a Rigel bug** — the fallback worked exactly as designed. It's
whatever set `ANTHROPIC_BASE_URL` globally in this shell (possibly a
side effect of another tool's environment, e.g. a Claude Code session
config) applying to unrelated apps like Rigel. If you want Rigel's Claude
provider to reach the real cloud API on a machine where `ANTHROPIC_BASE_URL`
is set for another purpose, launch the sidecar with it explicitly cleared:
```bash
env -u ANTHROPIC_BASE_URL ./.venv/bin/python -m sidecar
```
Verified end-to-end against the real Anthropic API with this override
removed — see the Testing Strategy section below.

## Future Improvements
- Multi-turn context (send recent history to the LLM).
- Streaming replies.
- A live Ollama capability check (actually load-test a model) instead of
  the current size/RAM heuristic.

## Testing Strategy
- Manual, via `curl` against the sidecar directly and via the Settings UI
  in the browser — see the checklist in
  [`docs/features/llm-brain.md`](../features/llm-brain.md). No automated
  test suite exists yet in this repo for either the sidecar or the desktop
  app.
- Claude path was verified against the **real Anthropic cloud API** (not
  just the stub-fallback path) by explicitly clearing this machine's
  `ANTHROPIC_BASE_URL` override for the test call — confirmed a genuine,
  non-canned reply plus correctly split multi-intent commands (e.g. "open
  VS Code and also delete scratch.txt" → two separate `open_app`/
  `delete_file` commands with clean `{"target": ...}` args).

## References
- [`docs/features/llm-brain.md`](../features/llm-brain.md)
- [`docs/api/llm-settings-endpoints.md`](../api/llm-settings-endpoints.md)
- Anthropic structured outputs: `output_config.format` (GA, no beta header)
- Ollama `/api/chat` `format: "json"` and `/api/tags`
