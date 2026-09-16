# API Endpoint: LLM Brain Settings

## Overview
Three endpoints backing the Settings window's Brain tab: read/write the
persisted provider choice, and live-probe what's actually available
(Claude key status, installed Ollama models + fit-for-this-machine).

---

## `GET /api/rigel/settings/llm-config`

Returns the persisted LLM brain config, or defaults if never saved.

### Response (200)
```json
{
  "provider": "stub",
  "claude_model": null,
  "ollama_model": null,
  "ollama_host": "http://localhost:11434"
}
```
`ollama_host`'s default reflects `OLLAMA_API_URL`/`OLLAMA_HOST` if set in
the sidecar's environment (see the architecture doc), else the stock
`http://localhost:11434`.

---

## `POST /api/rigel/settings/llm-config`

Saves the LLM brain config. Takes effect on the next chat turn.

### Request Body
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `provider` | string | yes | One of `"stub"`, `"claude"`, `"ollama"`. |
| `claude_model` | string | if `provider: "claude"` | One of `claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5`. |
| `ollama_model` | string | if `provider: "ollama"` | Name as reported by `ollama list` / `/api/tags`, e.g. `llama3.2:latest`. |
| `ollama_host` | string | no | Default `http://localhost:11434` (or env-derived). |

```json
{
  "provider": "ollama",
  "ollama_model": "llama3.2:latest",
  "ollama_host": "http://localhost:11434"
}
```

### Response
- **200:** `{"ok": true}`
- **400:** invalid `provider`, missing `claude_model`/`ollama_model` for
  the chosen provider, or empty `ollama_host`.

```bash
curl -X POST http://127.0.0.1:5140/api/rigel/settings/llm-config \
  -H "Content-Type: application/json" \
  -d '{"provider": "claude", "claude_model": "claude-sonnet-5"}'
```

---

## `GET /api/rigel/settings/llm-options`

Live-probed data for the Settings UI to render — never reads from the
`settings` table, always reflects the current environment.

### Parameters
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `ollama_host` | string (query) | no | Override the host to probe, e.g. for a remote Ollama. Defaults to the same env-derived default as `llm-config`. |

### Response (200)
```json
{
  "claude": {
    "models": ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"],
    "api_key_configured": false
  },
  "ollama": {
    "installed": true,
    "binary_present": true,
    "host": "http://localhost:11434",
    "models": [
      {"name": "llama3.2:latest", "size_gb": 1.9, "fit": "comfortable"},
      {"name": "gemma4:26b", "size_gb": 16.8, "fit": "too_large"}
    ],
    "system_ram_gb": 16.0
  }
}
```
`fit` is one of `comfortable` (<50% of system RAM), `borderline` (<80%), or
`too_large`. When Ollama isn't reachable, `installed` is `false`;
`binary_present` distinguishes "not installed" (`false`) from "installed
but not running" (`true`, e.g. `ollama serve` hasn't been started).

### Examples

```bash
curl http://127.0.0.1:5140/api/rigel/settings/llm-options
curl "http://127.0.0.1:5140/api/rigel/settings/llm-options?ollama_host=http://localhost:12434"
```

## Notes
- This endpoint never raises on a down/missing Ollama — a failed probe just
  produces `{"installed": false, ...}` so the UI can show setup
  instructions instead of an error state.
- No rate limiting; calls are cheap (a 1.5s-timeout local HTTP probe + a
  `psutil` memory read).
- Related: [`docs/features/llm-brain.md`](../features/llm-brain.md),
  [`docs/architecture/llm-provider-selection.md`](../architecture/llm-provider-selection.md).
