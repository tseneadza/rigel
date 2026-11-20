# PRD: Rigel View Screens

**Status:** In Progress (v6), P1 built on `feature/rigel-view-screens` (`ad142d7`, not merged) · **Owner:** Tony · **Last updated:** 2026-11-18
**Open items:** Keyboard shortcuts, image-generation source, server refresh interval, brain chip detail (§10). Mockup v9 (v8 plus a hover-only brain chip) is approved. P1 defers FR-31 (fallback state) and FR-32 (click chip → Settings), and Tony still has to confirm M1 vs. FR-9 (docked orb in Agent Chat). P2–P5 not started.
**Location:** `docs/prd/rigel-view-screens.md` in the Rigel repo (mirror). Vault home: `01 - Projects/Rigel/Rigel View Screens PRD.md`.

---

## 1. Problem

Rigel today is a single surface: the orb plus a chat console. Two things are missing:

1. **No place to show content other than chat.** Toolbox state has no graphical home, and Rigel cannot present results in a richer form (for example, a generated image) without dumping them into the chat transcript.
2. **No basic session and device controls.** There is no way to start a fresh conversation without restarting the app, no way to stop Rigel listening without quitting, no full-screen mode, and no menu bar.

## 2. Goals

- G1. Give the main area a view switcher with three views: **Agent Chat**, **Toolbox**, and **Presentation**.
- G2. Keep the orb visible as a minimized, docked presence over every view, so the conversation continues.
- G3. Let Rigel present content (text, generated images) in the Presentation view.
- G4. Let the user start a new chat, mute the microphone, and enter full screen from the UI.
- G5. Show each ToolBox server's state from a dropdown on the "ToolBox · N servers" control.
- G6. Provide an application menu bar that exposes the same actions.
- G7. Always show which brain is answering: provider, model name, and Cloud or Local.

## 3. Non-goals (v1)

- Charts, graphs, or interactive HTML widgets in the Presentation view (deferred to v2).
- Real OS-level command execution (still deferred in the README).
- Changing the persona or the voice (covered by the persona work).
- A "Clear" action distinct from New Chat (dropped; see §5.5).

## 4. Users and primary flows

Single user: Tony, on his own Mac. Primary flows:

- **Ask Rigel to show something.** "Show me the Toolbox." Rigel switches to the Toolbox view. The orb stays in the corner.
- **Rigel presents a result.** Rigel puts a generated image or formatted text in the Presentation view and says what it did.
- **Start over.** Tony clicks "New Chat" or uses the Conversation menu. The LLM forgets prior turns. The old transcript stays browsable.
- **Stop listening.** Tony mutes Rigel's ears. The wake word is ignored. Spoken approvals still work.
- **Check the toolbox.** Tony opens the "ToolBox · N servers" dropdown and sees each server's state.

## 5. Functional requirements

### 5.1 View area and view switcher

- **FR-1.** The main view area has a view dropdown with three entries: **Agent Chat**, **Toolbox**, **Presentation**.
- **FR-2.** Agent Chat is the default view. It is the current chat console.
- **FR-3.** The Toolbox view shows the graphical representation from the ToolBox Live view tab.
- **FR-4.** The Presentation view shows content Rigel has chosen to present. It is empty until Rigel presents something. The most recent item stays visible until replaced.
- **FR-5.** Switching views does not clear chat state, and the view-switch control stays in the same place in every view.

### 5.2 Rigel changing views (decided)

- **FR-6.** Tony can request a view change by voice or by typing (for example, "show the Toolbox", "present that").
- **FR-7.** View-change authority (decided; was assumed in v2):
  - **Free switching** to and from Agent Chat and Presentation. Rigel may do this without asking.
  - **Confirmed switching** to the Toolbox view. Rigel proposes the switch and waits for a click or a spoken yes.
- **FR-8.** When Rigel switches the view on its own, it says so in the chat with one line (for example, "Switched to Toolbox.").

### 5.3 Orb behavior

- **FR-9.** When a non-chat view is active, the orb is docked in a small corner over the view. It stays visible and animates as it does today.
- **FR-10.** Tony can still talk to Rigel with the orb docked. Voice and typed input work in every view.
- **FR-11.** The existing auto-minimize-while-working behavior and the ⌘⇧R toggle keep working. The docked corner orb is the minimized state.

### 5.4 Presentation view content (v1)

- **FR-12.** The Presentation view renders formatted text (headings, lists, code blocks) and images.
- **FR-13.** Rigel can display **generated images**. The image source is whatever the brain produces. How generation is triggered is out of scope here (§10 Q7).
- **FR-14.** Each presented item has a title and a timestamp. Items are kept in the local store.
- **FR-14a.** Charts and interactive HTML widgets are v2 (deferred by decision).

### 5.5 New chat

- **FR-15.** A "New Chat" action (button and menu item) starts a fresh LLM context. Prior turns are not sent to the model.
- **FR-16.** The previous transcript is kept in the log and is reachable from a history list. Nothing is deleted.
- **FR-17.** The new chat becomes the active chat. The Agent Chat view shows an empty transcript.

### 5.6 Microphone: wake-word off

- **FR-18.** A "Mute Rigel's ears" control turns off wake-word listening. The mic stays open for approvals.
- **FR-19.** While muted, Rigel does not start a command from the wake word or from casual speech. A pending approval can still be answered yes/no by voice.
- **FR-20.** The muted state persists across relaunch. The control shows the current state clearly (for example, a crossed-out ear icon).
- **FR-21.** Typed input is never affected by mute.

### 5.7 Full screen

- **FR-22.** A "Full Screen" action uses the macOS native full-screen Space. The menu bar and Dock hide while it is active.
- **FR-23.** The action is also available in the View menu and the view dropdown area.

### 5.8 ToolBox server dropdown

- **FR-24.** The "ToolBox · N servers" control opens a dropdown listing every configured server.
- **FR-25.** Each row shows (ToolBox's own labels, copied exactly from its dashboard):
  - a status: **running** (ready to answer), **starting**, **stopping**, or **not running**;
  - the server's tool count;
  - a one-line error reason, shown only when the server is not running.
- **FR-26.** Status updates while the dropdown is open. The exact refresh interval is open (§10 Q8).
- **FR-26a.** No Reconnect button in v1. Keeping rows lean was the chosen tradeoff.

### 5.9 Menu bar

- **FR-27.** The app has an application menu bar with these menus:
  - **Rigel:** Settings, About, Quit.
  - **View:** Agent Chat, Toolbox, Presentation, Full Screen.
  - **Conversation:** New Chat, Mute Rigel's Ears (toggle).
  - **ToolBox:** Server status (opens the dropdown), Toolbox view.
- **FR-28.** Each menu action matches a control in the UI. Shortcuts for each are open (§10 Q6).

### 5.10 Brain indicator

- **FR-29.** A brain chip sits in the bottom-right corner of the window, directly above the docked orb, in every view. Format: `<provider> · <model> · <Cloud|Local>`. Examples: `Claude · claude-haiku-5-5 · Cloud`, `Ollama · <model> · Local`, `Basic · built-in · Local`.
- **FR-30.** Location rule: Claude is Cloud. Ollama is Local when its host is a loopback address (localhost or 127.0.0.1), and Network when it points at another machine. Basic has no model and is Local.
- **FR-31.** When the chosen brain fails and Rigel falls back to Basic (today's behaviour on an LLM error), the chip switches to a fallback state: `Fallback · Basic`, with the failure reason on hover. Replies produced by the fallback are marked in the transcript.
- **FR-32.** Clicking the chip opens Settings → Brain. A change there updates the chip immediately, without a restart.

## 6. Non-functional requirements

- **NFR-1.** Switching views completes in under 150 ms on the reference Mac.
- **NFR-2.** Mute state survives relaunch and is stored in Rigel's `settings` table (the existing store).
- **NFR-3.** Sidecar changes stay behind the existing desktop↔sidecar message format. Any new message type goes through the documented IPC contract.
- **NFR-4.** A new chat or mute never drops an in-flight approval.
- **NFR-5.** The Presentation view never executes content it presents. Images render; text renders as text.

## 7. Data and state

- `settings`: `mic_wake_word_enabled` (bool, default true), `active_view` (enum), `orb_corner` (existing).
- Conversations: a `conversations` table or a `conversation_id` on turns. A new chat sets the active `conversation_id`. Old turns keep theirs.
- Presentation items: `presentations` table (id, title, kind = text | image, body or image path, created_at, conversation_id).
- ToolBox status: derived at runtime from the gateway; not persisted.

*Schema changes need the database-schema-integrity procedure before any migration is written.*

## 8. Mockups

Mockups are required before any code is written (per Tony's standing rule). Status: **v8 produced (M1–M6); v9 approved.** `docs/mockups/mockup-v8-rigel-view-screens.html` and `Claude outputs/mockup-v9-rigel-view-screens.html`; both are mirrored in the Rigel vault under `Mockups/`.

- M1. Full window, Agent Chat view, with the view dropdown open, the orb docked, and the brain chip in the bottom-right corner.
- M2. Toolbox view with the orb docked in the corner.
- M3. Presentation view with a generated image and a text item.
- M4. Menu bar expanded (all four menus).
- M5. ToolBox server dropdown with running, starting, and not running rows, using ToolBox labels, including the error line and tool count.
- M6. Mute state: ear icon on, and muted (wake word off, approval still active).

## 9. Acceptance criteria

- AC-1. Selecting each view in the dropdown shows the correct content, and the orb stays visible in the corner.
- AC-2. Saying "show the Toolbox" triggers the confirmation card. Confirming switches the view.
- AC-3. A generated image appears in the Presentation view and survives a relaunch.
- AC-4. New Chat clears LLM context (verified by asking a follow-up that depends on a prior turn) while the old transcript stays in history.
- AC-5. With mute on, saying "Rigel" does nothing, and a pending approval still accepts a spoken yes.
- AC-6. Full Screen enters the native macOS Space and exits cleanly.
- AC-7. Each server row shows the correct state and tool count. A server stopped during a test changes to not running and shows its error line.
- AC-8. Every menu item has a matching in-app control and does the same thing.
- AC-9. The brain chip shows the active provider, model, and Cloud or Local. Forcing an unreachable Claude key or Ollama host shows the fallback state.

## 10. Open questions

1. ~~View autonomy split.~~ **Resolved:** free switching for Agent Chat and Presentation, confirmation for Toolbox.
2. ~~"Warm" definition.~~ **Resolved** from the ToolBox repo: not a separate state (see FR-25).
3. ~~Charts and HTML in v1.~~ **Resolved:** deferred to v2.
4. ~~Server row contents.~~ **Resolved:** status, tool count, and a one-line error when not running. No Reconnect in v1.
5. ~~"Clear" vs New Chat.~~ **Resolved:** same action; "Clear" dropped.
6. **Keyboard shortcuts.** For New Chat, Mute, Full Screen, and view switches. Only ⌘⇧R exists today.
7. **Generated images.** Which component generates them (the brain via a tool, or another path)? It decides how the Presentation view receives them.
8. **Refresh interval** for the server dropdown while open.

9. **Chip detail.** Show the full model id (for example `claude-haiku-5-5`) or a short name? Proposed: full id, since it is what Settings already stores.

## 11. Phasing (proposed)

- **P1.** View dropdown and Agent Chat / Toolbox / Presentation views. Docked orb.
- **P2.** New Chat and history. Mute (wake word off). Persisted state.
- **P3.** ToolBox server dropdown with states, tool counts, and error lines.
- **P4.** Presentation view with text and generated images. Rigel-initiated view switching.
- **P5.** Menu bar and Full Screen.

Each phase starts with its mockups approved.

## 12. Related docs

- `docs/features/orb-minimize.md`, `docs/features/toolbox.md`, `docs/features/voice-pipeline.md`, `docs/features/menu-actions.md`
- `docs/CONTINUATION.md`

## Revision history

- **v1 (2026-11-18):** Draft from interview answers.
- **v2 (2026-11-18):** Resolved Q3, Q4, Q5. Removed Clear. Status set to In Review. Q1 assumption recorded.
- **v3 (2026-11-18):** View-switch split confirmed. Status set to In Progress (design phase). Vault status set to active.
- **v4 (2026-11-18):** Server states aligned to ToolBox. "Warm" is the keep-warm timer, not a state. "Warm" definition resolved.
- **v5 (2026-11-18):** Brain indicator added (G7, FR-29 to FR-32, AC-9, M1, open question 4).
- **v6 (2026-11-18):** Brain chip moved to the bottom-right corner, above the docked orb. Icon key added to the mockup.
