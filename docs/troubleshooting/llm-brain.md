# Troubleshooting Guide: LLM Brain (Claude / Ollama)

## Quick Diagnosis

```
Chat reply is the exact canned stub text
("Understood. I would ... but command execution is not wired up yet...")
even though you selected Claude or Ollama in Settings?
│
├─ YES → the provider call failed and brain.py fell back to the stub.
│        Check the sidecar's console output for a line like:
│        "Claude brain failed (...); falling back to stub."
│        "Ollama brain failed (...); falling back to stub."
│        → find the specific error text below.
│
└─ NO, reply looks LLM-generated but Settings shows the provider as
   unreachable/not configured → see "Settings shows wrong status" below.
```

## Common Issues

### Issue: Claude calls silently go to the wrong place / "model not found"
**Symptoms:** Sidecar log shows
`Claude brain failed (Claude API error (404): ... model 'claude-...' not
found ...); falling back to stub.`

**Diagnosis:**
```bash
echo "$ANTHROPIC_BASE_URL"
```
If this prints anything, `anthropic.Anthropic()` is routing **all** Claude
calls there instead of the real Anthropic API — this is documented SDK
behavior, not a Rigel bug. We hit this for real during development: a
shell had `ANTHROPIC_BASE_URL=http://localhost:12434` (the same port as a
local Ollama install), so every "Claude" call was actually landing on
Ollama, which doesn't recognize model IDs like `claude-sonnet-5` → 404.

**Solutions:**
1. If you don't need the override for Rigel, launch the sidecar with it
   cleared:
   ```bash
   env -u ANTHROPIC_BASE_URL ./.venv/bin/python -m sidecar
   ```
2. If you *do* need it (an intentional enterprise/self-hosted proxy),
   confirm that proxy actually serves the model IDs in
   `llm_providers.CLAUDE_MODELS` (`claude-opus-5`, `claude-sonnet-5`,
   `claude-haiku-4-5`) — a proxy scoped for something else (like another
   local tool's internal traffic) may not.

### Issue: `Claude credentials not configured` in the sidecar log
**Symptoms:** `Claude brain failed (Claude credentials not configured: ...
Could not resolve authentication method ...); falling back to stub.`

**Diagnosis:** Rigel looks in the Keychain first, then the environment.
```bash
security find-generic-password -s rigel-anthropic-key >/dev/null && echo found || echo missing
curl -s 127.0.0.1:5140/api/rigel/settings/llm-options | grep -o '"api_key_source":[^,}]*'
```
`missing` means there's no Keychain item under that exact name (check the
*service* / "Keychain Item Name", not the account). If you set
`RIGEL_KEYCHAIN_SERVICE`, look up that name instead.

**Solutions:** save the key (copy it to the clipboard first), then restart
the sidecar. The key is cached after the first read, so a key added or
rotated while the sidecar is running isn't seen until a restart.
```bash
k=$(pbpaste); printf 'add-generic-password -U -s rigel-anthropic-key -a "$USER" -w "%s"\n' "$k" | security -i; unset k
```
The env-var fallback (`ANTHROPIC_API_KEY`) still works, but only in the
exact shell that launched the sidecar.

### Issue: Settings says there's no API key but you know one is saved
**Cause:** usually one of: the Keychain item has a different name than
`rigel-anthropic-key`; it's in a keychain other than *login*; or the
sidecar was started before the item was saved (restart it). The first time
the sidecar reads the item, macOS may ask to allow access — choose
**Always Allow**, or the read fails silently and Rigel falls back to the
environment.

### Issue: Ollama shows `installed: false` in Settings
**Diagnosis:**
```bash
curl http://127.0.0.1:5140/api/rigel/settings/llm-options | python3 -m json.tool
```
Check the `ollama.binary_present` field:
- `binary_present: false` → Ollama isn't installed on this machine at
  all. Install from [ollama.com](https://ollama.com).
- `binary_present: true`, `installed: false` → the binary exists but
  isn't currently serving. Run `ollama serve` (or open the Ollama app)
  and hit Refresh in Settings.

Also check the host being probed — `ollama.host` in that same response.
If it's not where your Ollama actually listens, see "Ollama on a
non-default port" below.

### Issue: Ollama on a non-default port isn't detected
**Symptoms:** `ollama list` works fine in your terminal, but Rigel's
Settings says Ollama isn't installed.

**Diagnosis:**
```bash
echo "$OLLAMA_HOST"        # e.g. 0.0.0.0:12434
echo "$OLLAMA_API_URL"     # e.g. http://localhost:12434
```
Rigel derives its default probe target from `OLLAMA_API_URL` first, then
`OLLAMA_HOST`, then falls back to `http://localhost:11434`. If neither is
set in the sidecar's environment, it'll probe the wrong port.

**Solutions:**
- Export `OLLAMA_API_URL` (or `OLLAMA_HOST`) in the shell that launches
  the sidecar, then restart it — same env-inheritance caveat as the
  Claude key above.
- Or just type the correct host into the **Host** field on the Ollama
  tab in Settings and hit Refresh — this overrides the default for that
  session without touching your shell's env.

### Issue: Model produces empty/wrong `args` for a detected command
**Symptoms:** A command intent is logged but `args` is `{}` even though
you clearly named a target ("open Chrome" → `args: {}`).

**Cause:** this is a model instruction-following limitation, not a
parser bug — smaller local Ollama models are less reliable at following
the `args_json` structured-output convention than Claude (Ollama's
`format: "json"` only guarantees valid JSON, not schema conformance).
`_normalize_command()` degrades gracefully to `{}` rather than crashing.

**Solutions:**
- Try a larger/more capable local model (check the fit label in Settings
  first — don't jump straight to a ❌ model).
- Or switch to Claude for more reliable structured output.

### Issue: `output_config.format.schema` 400 error (only relevant if
modifying `RESPONSE_SCHEMA` yourself)
**Symptoms:** `invalid_request_error: ... 'additionalProperties' must be
explicitly set to false`.

**Cause:** Claude's structured-output validator requires every `object`
schema node to set `additionalProperties: false`. This is why command
arguments travel as `args_json` (a plain string), not a nested `args`
object — a nested object would need `additionalProperties: false`, which
would force it to always be `{}`. If you add new fields to
`RESPONSE_SCHEMA` in `sidecar/llm_providers.py`, keep this constraint in
mind for any new `object`-typed node.

## Advanced Debugging

### Watch the fallback happen live
```bash
./.venv/bin/python -m sidecar   # run in foreground, don't backgrounding it
```
Every provider failure logs a `WARNING`-level line naming the exact
exception before falling back — this is the fastest way to see what's
actually wrong, faster than guessing from the (identical-looking) stub
reply in the UI.

### Test a provider directly, bypassing the HTTP layer
```bash
./.venv/bin/python -c "
from sidecar import llm_providers as lp
print(lp.claude_respond('open Chrome', 'claude-sonnet-5'))
"
./.venv/bin/python -c "
from sidecar import llm_providers as lp
print(lp.ollama_respond('open Chrome', 'llama3.2:latest', 'http://localhost:11434'))
"
```
This isolates whether the problem is in the provider call itself or in
the sidecar's HTTP/settings wiring around it.

## Resources
- [Setup Guide](../setup/llm-brain.md)
- [Feature Doc](../features/llm-brain.md)
- [Architecture Doc](../architecture/llm-provider-selection.md)
- [API Reference](../api/llm-settings-endpoints.md)
