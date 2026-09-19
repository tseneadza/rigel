# Feature: Expanded App-Operation Control

## Overview
Rigel currently detects open/close app intents and executes them through an
approval-gated execution layer, with a per-action/target whitelist to skip
approval for trusted commands (`sidecar/executor.py`,
`desktop/src/components/CommandApproval.jsx`,
`desktop/src/components/WhitelistSettings.jsx`). This proposal is about
going further: giving the user finer-grained control over *how* Rigel
operates the apps it opens — not just launching/quitting them, but things
like focusing/switching windows, minimizing/resizing, listing what's
currently running, and app-specific actions — using the same
intent-parse → approval-gate → execute pattern already in place.

This doc also records a verification done alongside the proposal: at the
time of writing, `main` (`feda36d`) already contains the approval-gated
execution layer, the whitelist feature, and the close/quit/kill intent fix
from the prior session — confirmed merged and pushed, nothing outstanding.

## Status
- [x] Incubating
- [ ] Planned
- [ ] In Development
- [ ] Alpha/Beta
- [ ] Production

## User-Facing Description
Today, a user can ask Rigel to open or close an app, and (depending on
whitelist config) either approve the action once or have it run
automatically. This proposal extends that to richer operations, e.g.:

> **User:** "Rigel, switch to Chrome." / "Minimize VS Code." / "What's
> running right now?"

All still routed through the same approval gate and whitelist users already
configure in Settings.

## Technical Implementation

### Architecture
Builds on the existing pipeline, no new components required — only new
intent types and matching OS-hook handlers:

```
User prompt → brain.py (intent parsing)
            → executor.py (approval gate + whitelist check)
            → OS-hook handler (new: focus/minimize/resize/list, in addition
              to existing open/close/file-CRUD)
            → db.py command_attempts log
```

### Key Components
- **Frontend:** `CommandApproval.jsx` (approval prompt — would need new
  copy for non open/close actions), `WhitelistSettings.jsx` (whitelist UI —
  would need new action types)
- **Backend:** `sidecar/brain.py` (intent parsing — needs new intent
  categories), `sidecar/executor.py` (execution + approval gate — needs new
  handlers per platform)
- **Storage:** existing `command_attempts` table in `~/.rigel/rigel.db`
  (no schema change needed if action/target stay generic strings)
- **APIs:** existing `/api/rigel/*` routes in `sidecar/app.py`

### Data Flow
1. User asks for a non open/close operation (e.g. "minimize Chrome")
2. `brain.py` classifies the intent (new category alongside open/close/file-CRUD)
3. `executor.py` checks the whitelist; if not whitelisted, surfaces an approval prompt
4. On approval, a platform-specific OS-hook handler performs the operation
5. Result is logged to `command_attempts`, same as today

## Configuration
No new environment variables anticipated; whitelist entries would gain new
action types (e.g. `focus`, `minimize`, `resize`) alongside the existing
`open`/`close`.

## Usage Examples

### User Perspective
```
User prompt: "Rigel, minimize Chrome."
Rigel response: "Understood. I would minimize Chrome — but this action type
isn't wired up yet, so I've logged the intent instead."
```

### Developer Perspective
```python
# sidecar/executor.py — sketch of a new handler alongside existing
# open/close/file-CRUD handlers
def handle_window_action(action: str, target: str) -> ExecutionResult:
    ...
```

## Testing
- **Manual Testing Checklist:**
  - [ ] New intent types are correctly classified by `brain.py`
  - [ ] Approval gate fires for non-whitelisted window actions
  - [ ] Whitelisted window actions skip approval
  - [ ] Command attempt is logged regardless of approval outcome

## Known Limitations
- Real execution for open/close/file-CRUD is itself still early (per
  README's "Project Status" section); window-level control (focus,
  minimize, resize, enumerate running apps) is not implemented at all yet.
- Platform differences (macOS/Windows/Linux) mean OS-hook handlers likely
  need per-platform implementations, same as the voice pipeline already does.

## Future Enhancements
- Focus/switch to a running app's window
- Minimize/restore/resize a specific app's window
- List currently running apps/windows as a Rigel query
- App-specific actions beyond generic window ops (e.g. "new tab in Chrome")

## Related Features
- Approval-gated execution layer for open/close app + file CRUD (`sidecar/executor.py`)
- Per-action/target whitelist (`desktop/src/components/WhitelistSettings.jsx`)

## References
- `sidecar/executor.py`
- `sidecar/brain.py`
- `desktop/src/components/CommandApproval.jsx`
- `desktop/src/components/WhitelistSettings.jsx`
- `README.md` — "Project Status" section (real command execution deferred slice)
