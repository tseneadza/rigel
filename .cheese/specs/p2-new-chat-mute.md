---
status: approved
phase: P2
prd: docs/prd/rigel-view-screens.md
branch: feature/rigel-view-screens-p2
base: ad142d7
mockups: "New Chat: v10 (drafted 2026-11-18, awaiting Tony). Mute: v8 M6 (v9 approved set)."
---

# P2: New Chat, history, and mute (Rigel View Screens)

## Goal

Tony can start a fresh chat (the LLM forgets prior turns, the transcript stays in history) and mute Rigel's wake word (approvals still work by voice). Both states persist across relaunch.

## In scope (PRD FR-15 to FR-21, NFR-2, NFR-4)

- **FR-15** A "New Chat" action (header button and Conversation menu item) starts a fresh LLM context. Prior turns are not sent to the model.
- **FR-16** The previous transcript is kept and reachable from a history list. Nothing is deleted.
- **FR-17** The new chat becomes the active chat. Agent Chat shows an empty transcript.
- **FR-18** "Mute Rigel's ears" turns off wake-word listening. The mic stays open for approvals.
- **FR-19** While muted, Rigel does not start a command from the wake word or casual speech. A pending approval can still be answered yes or no by voice.
- **FR-20** The muted state persists across relaunch. The control shows the state (crossed-out ear icon when muted).
- **FR-21** Typed input is never affected by mute.
- **NFR-2** Mute state is stored in the existing `settings` table as `mic_wake_word_enabled` (bool, default true).
- **NFR-4** A new chat or mute never drops an in-flight approval.

## Out of scope

- Keyboard shortcuts (PRD §10 Q6, open).
- Full Screen, menu bar, ToolBox server dropdown (P3, P5).
- Presentation content and Rigel-initiated switching (P4).

## Acceptance criteria (PRD AC-4, AC-5, plus persistence)

- **AC-4** New Chat clears LLM context: a follow-up that depends on a prior turn gets no answer from prior context. The old transcript stays in history.
- **AC-5** With mute on, saying "Rigel" does nothing. A pending approval still accepts a spoken yes.
- **AC-P2-1** Mute state survives a relaunch (read from `settings`).
- **AC-P2-2** The New Chat button and the menu item do the same thing (AC-8 for these two items).
- **AC-P2-3** Typed input works while muted.

## Verification (what must be checked on the real path)

- Gates: `npx vite build` and `npm test` in `desktop/`; `.venv/bin/python -m pytest` in the repo root (sidecar).
- Browser (manual, Chrome at `localhost:1425` with the sidecar running): New Chat clears the transcript view; mute toggles the icon; both survive a reload.
- Voice path (manual): mute, say "Rigel", confirm nothing starts. Approval by voice still works.

## Open decisions (must be answered before this spec is approved)

Decision 1 is answered. Decision 2 needs approval of v10. Decision 3 is open.

1. **Conversation storage: decided.** A `conversations` table (Tony, 2026-11-18). A schema change needs the `database-schema-integrity` procedure before any migration is written.
2. **New Chat mockup: drafted, awaiting approval.** v10 (`mockup-v10-new-chat.html`, shown 2026-11-18). Tony's approval is required before code.
3. **Voice-path skills.** Mute touches the wake-word path, so `voice-pipeline-integrity` and `intent-definition-integrity` apply. Confirm they should be followed for this phase.

## Phase constraints (from CLAUDE.md)

- Mockup before code: New Chat needs approval (decision 2).
- Interview on ambiguity: decision 1 is open.
- Branch `feature/rigel-view-screens-p2` from `ad142d7` when coding starts.
- Checkpoint `docs/CONTINUATION.md` (newest entry on top) when done.
