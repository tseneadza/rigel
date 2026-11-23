# Feature: ToolBox Tools (MCP gateway)

## Overview
Rigel's brain can now find and run tools through **ToolBox**, Tony's local MCP
gateway (`~/Codehome/ToolBox`, service at `http://127.0.0.1:8795`). ToolBox
catalogs every registered MCP server (osa-system, agentic-dev, filesystem,
git, gmail, macos, memory, weatherapi, time, …), starts a server only when one
of its tools is called, and unloads it when idle. Rigel connects as an MCP
client named **`rigel`** and shows up as an agent on ToolBox's dashboard.

Rigel's own actions (open/close app, create/delete file, app handlers, menu
actions) are unchanged and still go through `executor.py` and its approval
cards. ToolBox adds everything else.

Mockup: [`docs/mockups/toolbox-connect-v1.html`](../mockups/toolbox-connect-v1.html)
(approved 2026-11-15).

## Status
- [ ] Planned
- [ ] In Development
- [x] Alpha/Beta: built and verified on the real path (Claude and Ollama),
      including spoken approvals in the native app (see "Verified")
- [ ] Production

## Decisions (Tony, 2026-11-15)
- Slice 1 scope: the brain uses tools (`need` → `call`).
- Both brains: Claude and Ollama (Ollama only for models with tool calling).
- Approvals: console card **and** a spoken yes/no.
- Approvals wait **indefinitely** on Rigel's side. (A server can still give
  up: osa-system declines after `APPROVAL_TIMEOUT_S = 120`.)
- Spoken answers are read **flexibly**; if Rigel isn't sure, it asks a
  follow-up instead of guessing.
- Tool steps are **folded** into one "ToolBox · used N tools" line per reply.
- Rigel's own executor stays; ToolBox is additive.

## User-Facing Description
- Ask for anything a ToolBox server can do: "how's my battery?", "any new
  mail from Dana?", "what's the git status of rigel?". Under Rigel's reply, a
  line reads **ToolBox · used 1 tool**. Click it to see each step (the
  `need` search, each call, timings, and whether an approval was given).
- If a tool needs permission (e.g. osa-system's `fs.delete`), an amber
  **Approval needed** card appears with exactly what will run. Click
  **Approve** / **Decline**, or, with voice on, answer out loud: Rigel reads
  the request and listens once **without the wake word**. "Yes", "go ahead",
  "sure" approve; "no", "cancel", "stop" decline; anything unclear ("hold on",
  "maybe", "what is it?") gets a follow-up question. Rigel expands out of its
  minimized orb while a card is waiting.
- Header badge: **ToolBox · 9 servers** (green) or **ToolBox offline** (red).
  When ToolBox is down, Rigel says so instead of guessing, and the reply
  shows a "ToolBox unreachable" chip.
- Settings → Brain → **ToolBox**: on/off, address (auto-found from
  `~/.toolbox/service.json`), live status, whether the selected brain can use
  tools, and max tool steps per reply (default 5).

## Technical Implementation

### Flow
```
Desktop ──/chat──▶ brain.respond_with_tools
                     └─ tool_brain.respond (Claude or Ollama tool loop)
                          tools: toolbox_need · toolbox_call · respond
                          └─ toolbox_client (MCP over HTTP, clientInfo "rigel")
                               └─ ToolBox :8795 ─▶ osa-system, gmail, …

Approval: server elicitation ─▶ ToolBox ─▶ toolbox_client._on_elicit
          ─▶ approvals.open_approval (blocks the call)
          Desktop polls GET /toolbox/approvals while /chat is in flight
          ─▶ card + speak(spoken) + voice_listen_once
          ─▶ POST …/answer (click) or …/interpret (voice) ─▶ call resumes
```

### Files
| File | Role |
|---|---|
| `sidecar/toolbox_client.py` | One long-lived MCP session on its own asyncio thread; `need`, `call`, `status`; no read timeout on the stream (approvals can wait). |
| `sidecar/approvals.py` | Pending approvals, spoken summary, answer interpretation (keywords first, LLM only when unclear, never approves on doubt). |
| `sidecar/tool_brain.py` | Claude (`tool_choice: any`) and Ollama tool loops; step recording; guards (below). |
| `sidecar/brain.py` | `respond_with_tools()`: ToolBox path, offline/unsupported fallbacks, menu-action fallback only if no tools ran. |
| `sidecar/db.py` | New `tool_calls` table (additive; no tool output stored). |
| `desktop/src/components/ToolSteps.jsx` | Folded steps line + chips. |
| `desktop/src/components/ToolBoxApproval.jsx` | Approval card. |
| `desktop/src/components/ToolBoxSettings.jsx` | Settings → Brain → ToolBox. |
| `desktop/src-tauri/src/voice/{mod,listener}.rs` | `voice_listen_once`: record the next utterance without the wake word (6 s onset grace), only after TTS has stopped. |

### Small-model guards (all found live with llama3.1:8b / qwen2.5:7b)
- `toolbox_call` only runs tool names that `need` returned this turn; a
  guessed name is looked up and the real matches are handed back. A guess
  that differs only in punctuation is corrected to the real tool.
- Arguments put beside `tool` instead of inside `arguments` are folded in.
- A tool call written as text (`{"name": "toolbox_call", …}`) is executed.
- Paths are stripped from the `need` query (they drowned ToolBox's ranking).
- If tools were found but none called, the model is nudged once.
- The final reply is cleaned: leaked tool-call text is dropped; a false
  "waiting on your approval" or a claimed action that never ran is replaced
  with a factual summary of the steps.

### API (all under `/api/rigel`)
| Method | Path | Notes |
|---|---|---|
| POST | `/chat` | Response adds `tool_steps[]` and `toolbox: {state: used\|available\|offline\|unsupported\|disabled\|error, detail?}`. |
| GET | `/logs` | Rigel turns now carry `tool_steps` (rehydration). |
| GET/POST | `/settings/toolbox-config` | `{enabled, url (local only, null = auto), max_steps 1–15}`. |
| GET | `/toolbox/status` | `{state, url, servers, tools, brain: {provider, model?, tools}}`. |
| GET | `/toolbox/approvals` | Pending approvals: `{id, tool, server, message, spoken, status, …}`. |
| POST | `/toolbox/approvals/{id}/answer` | `{decision: approve\|decline, via: click\|voice\|typed}`; 409 if not pending. |
| POST | `/toolbox/approvals/{id}/interpret` | `{text, via}` → `{decision: approve\|decline\|unclear\|closed, follow_up?}`. |

## Verified (2026-11-15, real path on Tony's Mac)
- Client → ToolBox → osa-system: `need`, read-only `health.battery`; gated
  `fs.delete` declined (file kept) and approved (file deleted).
- `/chat` with Ollama: battery answered correctly via `need` + `call`;
  gated delete with an unclear spoken answer ("hmm what is that" → follow-up)
  then "yeah go ahead" → approved by voice, file deleted.
- Desktop (Vite dev in Chrome): folded steps, approval card, **Decline** click
  (file kept, honest reply), **Approve** click (file deleted, logged "approved
  by click"), offline badge + chip + honest reply, Settings section.
- ToolBox dashboard lists `rigel` as an agent with its calls.
- 58 sidecar tests (`./.venv/bin/python -m pytest -q sidecar/tests`); Vite
  build and `cargo check` clean.

- Claude (`claude-sonnet-5`, key from the Keychain, env key unset):
  battery answered via `need` + `call`; gated delete with an unclear answer
  → follow-up → "yeah go ahead" approved by voice (file deleted); "no, leave
  it" / "nope" declined by voice (file kept, honest reply).

- Native app, 2026-11-22 (Rigel.log): spoken approval end to end. The
  question was spoken, listen-once started without the wake word, Tony
  said "Yes, approved.", the delete was approved by voice, and Rigel's
  reply was not picked up by the mic. Click approvals made while Rigel was
  still asking cancel the listen before it starts.

- Native app, 2026-11-22: a click while the listen-once recording was running
  (04:55:36 to 04:55:38) logged `recording dropped (listen-once cancelled),
  2.52s discarded`, and Rigel's reply was not transcribed (`f3ba2fb`).

**Known gaps (desktop):** the "listening for your answer" bars appear when
listening is requested, while Rigel is still speaking, before recording
starts. A stray sound can also end the single listen-once early, after which
nothing listens again although the card still says it is listening. Small Ollama models are unreliable at calls that need
arguments; Claude is the recommended brain for ToolBox.

## API key (Claude)
The sidecar reads the Anthropic API key from the macOS Keychain, service
`rigel-anthropic-key` (`sidecar/keychain.py`; override the service name with
`RIGEL_KEYCHAIN_SERVICE`), falling back to `ANTHROPIC_API_KEY` in the
environment. The key goes straight to the Anthropic client and is never
logged, returned or shown; Settings → Brain → Claude says only where it came
from. Stored 2026-11-15 from Tony's shared Codehome key. To rotate it
without the key appearing on screen or in `ps`:

```sh
k=$(pbpaste); printf 'add-generic-password -U -s rigel-anthropic-key -a "$USER" -w "%s"\n' "$k" | security -i; unset k
```
Then restart the sidecar (the key is cached after the first read).

## Troubleshooting
- **Badge says "ToolBox offline"** → `toolbox status`; ToolBox runs as the
  launchd agent `dev.toolbox.service`. Settings → Brain → ToolBox shows the
  address Rigel is using.
- **Rigel answers without tools** → check `toolbox.state` in the `/chat`
  response: `unsupported` means the Ollama model has no tool calling
  (`ollama show <model>` → capabilities).
- **Approval card disappeared on its own** → the server stopped waiting
  (osa-system: 2 minutes). The step shows "server stopped waiting".
- **Spoken answer not heard** → voice must be on (Settings → Voice); listen-once
  starts after Rigel finishes speaking; see `~/.rigel/debug` dumps.
