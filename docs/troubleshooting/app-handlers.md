# Troubleshooting Guide: App Handlers (Chrome / VS Code)

## Quick Diagnosis

```
Asked Rigel for an in-app action ("new tab in Chrome to X",
"open ~/foo in VS Code") and nothing happened, or the reply
doesn't mention the app at all?
│
├─ Reply looks like the generic open_app reply instead
│  ("Understood... waiting on your approval to open app...")
│  → registry.match() didn't fire, or the handler's scoped call
│    returned no tool. See "Handler never produces an app_action" below.
│
├─ An approval card appeared ("chrome: new tab (...)") but
│  approving it errors →  see "Chrome/VS Code action fails on approve" below.
│
├─ You're not on macOS
│  → the whole execution layer (not just handlers) is unimplemented —
│    see "Not running on macOS" below.
│
└─ You're on the Ollama provider
   → app handlers only run under Claude — see "Ollama provider never
     produces app_action commands" below.
```

## Common Issues

### Issue: `code` CLI isn't on PATH
**Symptoms:** A VS Code `open_file`/`open_folder`/`new_window` approval
runs and comes back `status: "error"` with detail:
```
the 'code' CLI isn't on PATH — install it from VS Code's Command Palette:
Shell Command: Install 'code' command in PATH.
```
This is the exact string `vscode.py`'s `_CLI_MISSING` constant returns,
raised whenever `subprocess.run(["code", ...])` hits a `FileNotFoundError`
— i.e. `code` genuinely isn't resolvable on the sidecar process's `PATH`,
not a VS Code crash or a bad path argument.

**Diagnosis:**
```bash
which code   # empty output means it's not on PATH for this shell
```
Remember the same env-inheritance caveat documented for
`ANTHROPIC_API_KEY` in `docs/troubleshooting/llm-brain.md`: check this in
the exact shell/process that launched the sidecar, not just your
interactive terminal — a `code` that resolves in one terminal app may not
be visible to a sidecar started some other way.

**Solutions:**
1. In VS Code itself, open the Command Palette (`⌘⇧P`) and run:
   **Shell Command: Install 'code' command in PATH.**
2. Restart the sidecar from the same shell so it picks up the updated
   `PATH`:
   ```bash
   ./.venv/bin/python -m sidecar
   ```
3. Re-verify:
   ```bash
   which code && code --version
   ```
Note that `focus`/`minimize` for VS Code do **not** need the `code` CLI at
all — they go through `window_ops.py`'s AppleScript instead (see the
System Events process name issue below). Only `open_file`, `open_folder`,
and `new_window` depend on `code` being on `PATH`.

### Issue: VS Code `focus`/`minimize` report success but nothing visibly happens
**Symptoms:** Approving a `vscode: focus` or `vscode: minimize` command
comes back `status: "ok"` (`"Focused Visual Studio Code."` /
`"Minimized Visual Studio Code."`), but VS Code's window doesn't actually
come to the front or minimize.

**Cause — an unconfirmed judgment call.** `window_ops.focus`/`minimize`
need System Events' exact process name for the target app, and `vscode.py`
hardcodes `_PROCESS_NAME = "Code"` rather than the `"Visual Studio Code"`
display name — reasoned from how VS Code's `.app` bundle is laid out
(`Visual Studio Code.app/Contents/MacOS/Code` is the actual executable
name, and Activity Monitor / `ps` conventionally list a process by its
executable name, not its `Info.plist` `CFBundleName`). This reasoning has
**not been confirmed against a real running VS Code** — it's a judgment
call `vscode.py`'s own comment flags explicitly, not a verified fact.

**Diagnosis — confirm the real process name on the target machine:**
```bash
osascript -e 'tell application "System Events" to name of every process'
```
Run this with VS Code actually open, and look for either `"Code"` or
`"Visual Studio Code"` (or something else entirely, e.g. if Microsoft
changes the executable name in a future release) in the output.

**Solutions:**
- If the process name is confirmed as `"Code"`, this isn't a bug — check
  for something else blocking the AppleScript (System Events permission —
  see below).
- If the real name differs, update the `_PROCESS_NAME` constant near the
  top of `sidecar/handlers/vscode.py` to match, and re-run the diagnosis
  command above after the fix to confirm the corrected value actually
  works.
- If System Events AppleScript needs Accessibility/Automation permission
  on the target machine and hasn't been granted, `focus`/`minimize` may
  silently no-op rather than erroring cleanly — check System
  Settings → Privacy & Security → Automation, and allow the sidecar's
  Python process (or Terminal, if run from there) to control "System
  Events."

### Issue: Chrome `focus`/`minimize` behave the same way, unexpectedly
**Symptoms:** Same shape as the VS Code issue above, for Chrome.

**Cause:** `chrome.py` passes `self.display_name` ("Google Chrome") to
`window_ops.focus`/`minimize`, not a hardcoded constant like VS Code's —
Chrome's display name and its System Events process name are the same
string, so this path doesn't carry the same judgment-call risk `vscode.py`
does. If this still doesn't work, it's more likely the System Events
Automation permission (see above) than a wrong process name.

### Issue: `open_app`/`close_app` work for Chrome but in-app actions don't
**Symptoms:** "Open Chrome" and "quit Chrome" work fine (they always did —
that's the pre-existing generic path), but "new tab in Chrome" or "list my
Chrome tabs" produces no approval card and a generic-sounding reply.

**Cause:** most likely `registry.match()` never routed the utterance to
`ChromeHandler`, or the handler's scoped Claude call decided (correctly or
not) that nothing in its `tools` applied — see "Handler never produces an
app_action" below, which covers both apps.

### Issue: Handler never produces an `app_action`
**Symptoms:** No approval card for a request that should clearly map to a
Chrome or VS Code action; the reply is whatever the shared four-verb pass
or plain conversational reply already produced, with nothing extra.

**Diagnosis, in order:**
1. **Keyword match.** `registry.match()` is a plain substring match
   against `ChromeHandler.match_keywords = ["chrome", "google chrome"]` or
   `VSCodeHandler.match_keywords = ["vs code", "vscode", "visual studio
   code"]`. An utterance that never says one of those literal substrings
   (e.g. "open a new tab" with no app named) never reaches the handler at
   all — this is a known limitation of keyword matching, not a bug to
   chase.
2. **Provider.** App handlers only run when `llm_config.provider ==
   "claude"` — see "Ollama provider never produces app_action commands"
   below.
3. **The handler's own judgment.** Both handlers' system prompts
   explicitly instruct the model to call *no* tool when the request is
   really about launching/quitting the whole app rather than an in-app
   action, and to call no tool rather than guess when nothing clearly
   matches. "Open Chrome" correctly produces zero `app_action` commands —
   that's by design (see the architecture doc's "Secondary Flow"), not a
   failure.
4. **A silent Claude call failure.** Check the sidecar's console output
   for:
   ```
   App handler '<app_id>' call failed (...); skipping.
   ```
   which means `claude_app_action()` raised `LLMError` — same causes as
   any other Claude call failure (no `ANTHROPIC_API_KEY`,
   `ANTHROPIC_BASE_URL` pointed somewhere unexpected, rate limiting) — see
   `docs/troubleshooting/llm-brain.md`'s Claude-specific issues, which
   apply identically here since `claude_app_action()` uses the same
   `anthropic.Anthropic()` client construction as `claude_respond()`.

**Solutions:**
- Rephrase to include the app's name/keyword explicitly if step 1 is the
  cause.
- Switch to the Claude provider in Settings if step 2 is the cause.
- Nothing to fix if step 3 — that's correct behavior.
- Follow `docs/troubleshooting/llm-brain.md`'s Claude troubleshooting
  steps if step 4 is the cause.

### Issue: Ollama provider never produces `app_action` commands
**Symptoms:** Every in-app request (Chrome, VS Code) falls through to the
shared reply/four-verb pass only, even when phrased clearly, while the
same phrasing works under the Claude provider.

**Cause:** this is expected, not a bug. `_app_commands()` in
`sidecar/brain.py` is only called from the Claude branch of
`_respond_via_provider()` — `claude_app_action()` uses real Claude
tool-use, which the Ollama path's `format: "json"` JSON-mode prompting
has no equivalent for yet. This gap is noted directly in
`_app_commands()`'s own docstring as a documented future limitation, not
an oversight to work around.

**Solutions:**
- Switch to the Claude provider in Settings for app-handler actions;
  Ollama remains usable for everything else (the stub-equivalent
  four-verb pass and general conversation).
- No current workaround exists inside Rigel for Ollama — this is tracked
  as a Future Enhancement in the feature doc.

### Issue: Not running on macOS
**Symptoms:** Any `app_action` command comes back `status: "error"`,
detail: `"execution not implemented for platform '<platform>'."`

**Cause:** `executor.execute()` checks `sys.platform != "darwin"` before
dispatching to any action, `app_action` included — this predates the
handler framework and applies to the whole execution layer, not something
specific to Chrome/VS Code handlers.

**Solutions:** none within Rigel — the execution layer is macOS-only by
design (AppleScript via `osascript`, `open -a`, and now the `code` CLI are
all macOS-specific mechanisms). Detection/preview/whitelist-check still
work on any platform; only the final execution step is gated.

### Issue: Approval card renders with unreadable/empty detail text
**Symptoms:** `CommandApproval.jsx`'s card for an `app_action` shows just
`"chrome: new tab"` with nothing in parentheses, or shows raw object
syntax instead of a value.

**Diagnosis:** `CommandApproval.jsx`'s `describe()` builds the parenthetical
detail from `Object.values(tool_args ?? {}).filter(Boolean).join(", ")` —
i.e. it prints every non-empty value in `tool_args`, with no key labels.
For `new_tab({"url": ""})` (an empty/omitted URL, which is valid — Chrome
opens its default new-tab page), there's nothing to show, so
`"chrome: new tab"` with no parenthetical is the **correct** rendering,
not a bug. For a tool with more than one argument, values run together
separated by commas with no indication of which value is which field —
this is a real, acknowledged rendering limitation, not something to
diagnose further; neither current handler's tools have more than one
argument, so it hasn't come up yet in practice.

## Advanced Debugging

### Watch handler routing and Claude calls live
```bash
./.venv/bin/python -m sidecar   # run in foreground
```
Every handler-call failure logs a `WARNING`-level line naming the exact
exception, same pattern as the LLM brain's own fallback logging:
```
App handler '<app_id>' call failed (<exception>); skipping.
```

### Call a handler's scoped Claude request directly, bypassing HTTP
```bash
./.venv/bin/python -c "
from sidecar import llm_providers as lp
from sidecar.handlers import registry
import sidecar.handlers  # populate the registry via __init__ imports

handler = registry.get('chrome')
print(lp.claude_app_action('new tab to github.com', 'claude-sonnet-5', handler))
"
```
This isolates whether a problem is in the Claude tool-use call itself
(model choice, credentials, prompt) or in `brain.py`'s routing
(`registry.match()`) around it.

### Test a handler's `execute_tool` directly, bypassing preview/whitelist
```bash
./.venv/bin/python -c "
from sidecar.handlers import registry
import sidecar.handlers

handler = registry.get('vscode')
print(handler.execute_tool('open_folder', {'path': '~/projects/rigel'}))
"
```
Useful for isolating whether a failure is in `executor.py`'s
validation/whitelist layer or in the handler's own `osascript`/`code` CLI
call — macOS only, since this shells out for real.

### Confirm which handlers are actually registered
```bash
curl http://127.0.0.1:5140/api/rigel/handlers | python3 -m json.tool
```
If a handler you expect is missing entirely, check
`sidecar/handlers/__init__.py` imports its module — a handler that's never
imported never calls `registry.register()`, and so never appears here or
in `registry.match()`'s candidates.

## Known Gaps (not yet verifiable in this environment)
- The exact AppleScript/`code` CLI behavior above is written from reading
  `chrome.py`/`vscode.py`/`window_ops.py` and the source proposal doc's
  own notes, not from having run these commands against a real Chrome or
  VS Code — this development environment has no macOS. If a real-hardware
  run surfaces a different error string or behavior than documented here,
  trust the real output over this document and update it.
- The VS Code System Events process name (`"Code"` vs. `"Visual Studio
  Code"`) is explicitly unconfirmed, as described above — treat that
  section as the most likely thing to need a correction once someone runs
  this on a real Mac.

## Resources
- [Feature Doc](../features/app-handlers.md)
- [Architecture Doc](../architecture/app-handlers.md)
- [API Reference](../api/handler-endpoints.md)
- [LLM Brain Troubleshooting](llm-brain.md) — Claude credential/
  `ANTHROPIC_BASE_URL` issues apply identically to `claude_app_action()`
