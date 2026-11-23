# Rigel: Continuation

Read this first at the start of every Rigel session. Newest entry on top.

---

## Speaker verification: build started (2026-11-23 01:50, branch `feature/speaker-verification` off main)

- Approved by Tony: mockups v11 (settings) and v12 (enrollment) in `docs/mockups/`, decisions in `docs/specs/speaker-verification-and-settings-DRAFT.md`. Model download OK (ECAPA-TDNN ONNX, about 83 MB, first run).
- DONE (uncommitted): `sidecar/db.py` `voice_profiles` table (new table only, no backup needed) with `save_voice_profile`, `get_voice_profile`, `delete_voice_profile`. Tests `sidecar/tests/test_db_voice_profile.py`: 8 pass, plus the 6 conversation tests (14 total).
- DONE (uncommitted): `desktop/src-tauri/src/voice/speaker.rs`: cosine, best score over enrolled vectors, `is_enrolled_voice` (fails closed with no profile). `DEFAULT_THRESHOLD = 0.5` is a PLACEHOLDER until tuned. Six unit tests. Registered in `voice/mod.rs`. NOT compiled here: run `cargo test` on the Mac.
- Note: `stt.rs` on this branch was restored to `main` (the vocabulary change lives on `feature/stt-vocabulary`, commit 0ec87f9).
- Chose to proceed with the plan as written (sidecar sends the profile to the listener). Not yet built.
- NEXT (needs the Mac for Rust builds): (1) model loader in `desktop/src-tauri` via ONNX Runtime with checksum check; (2) embedding + match against the stored profile; (3) gate the listener and approvals on the match (drop non-matching transcripts before wake word or approval); (4) enrollment UI (v12) and settings UI (v11); (5) measure false accept/reject on Tony's recorded clips, including TV, then set the default threshold.
- Open design question for step 1: the profile lives in the sidecar DB, but matching runs in the Rust listener. Plan: sidecar serves the profile to the listener at start-up and after enrollment. Confirm before building.

## Speech-to-text: vocabulary hint + term fixes (2026-11-23, NOT committed, NOT on a branch yet)

- `desktop/src-tauri/src/voice/stt.rs`: Whisper initial prompt (`VOCAB_PROMPT`: Rigel, ToolBox, Codehome, Obsidian, scratch.txt, Tony Seneadza) and `fix_terms()`: exact whole-word fixes for observed mishearings ("Rigio", "Rigero", "rogeridol", "scratch.tit"). Unit tests added to the existing `tests` module.
- Not compiled or run. Run `cargo test` in `desktop/src-tauri` on the Mac, then test with the live mic.
- Git on this machine is blocked by stale lock files (`.git/index.lock`, `.git/HEAD.lock`). A leftover `.git/stale-index-lock-0600` was moved aside by hand. On the Mac, with no git running, delete the lock files, then create `feature/stt-vocabulary` from `origin/main` and commit this change.

## Voice approval fix: grunts must never approve (2026-11-23, branch `fix/voice-approval-noise`)

**Branch:** `fix/voice-approval-noise` (from `ec50782`) · **Not committed yet**. Commit when Tony asks.

**What happened (live, 00:24 local):** Tony asked "Use the toolbox to delete the scratch.txt file in my Rigio folder." The approval card then listened without a wake word and got four transcripts: "♪ Scenes from a house ♪ Eh.", "Here we go. Ugh.", "Goodbye, wow.", and "Mm-hmm" (no-speech probability 0.55). Tony was only grunting, but the last one was treated as "approved by voice" and scratch.txt was deleted. Tony did not click or say yes. The card never showed "click to answer".

**Cause (inferred; the log doesn't record the classifier's output):** `interpret()` in `sidecar/approvals.py` sends any unclear answer to the language model. Approvals use the same `llm_config` as the brain (saved brain: Ollama `minimax-h3-prompt-enhancer`, which the handoff describes as not a tool-use model). That model said "approve" for a grunt.

**Fix (in `sidecar/approvals.py`):**
- `_is_filler()`: grunts and hums ("mm", "hmm", "uh huh", "ugh", "huh") never reach the model and return `unclear`.
- A model "approve" is accepted only when the answer starts with a clear yes word (`_clear_yes_start`), with no negation and no hedge. Otherwise it is downgraded to `unclear`.
- Keyword "approve" and "decline" logic is unchanged. A long, clear yes still goes to the model, as before.

**Verified:**
- `sidecar/tests/test_approvals.py`: 56 pass on the Linux VM (pytest installed into `~/pytest-lib`, stdlib-only code). 14 of the new or changed tests fail on the old `HEAD` code, so they do catch this bug.
- Not run: the rest of the sidecar test suite (FastAPI and anthropic not installed here). Run `.venv/bin/python -m pytest` on the Mac before committing.
- **Not verified live.** Needs a retest with the TV muted.

**Known gaps (not fixed):**
1. A keyword yes from TV dialogue can still approve. Fixing this means gating listen-once transcripts on the speech-to-text no-speech probability in the Rust listener. That is a separate change.
2. `.claude/skills/approval-gate-validation` describes a Rust layout (`src/approval/gates.toml`, `engine.rs`) that doesn't exist in Rigel. The skill needs rewriting for the Python sidecar.
3. Speech-to-text hears "Rigel" as "Rigio" and "Rigero". Voice-pipeline work.
4. The speech threshold can stay high for minutes after a loud noise (rms spike near 00:14 raised it from 0.003 to about 0.03).

**Update 2026-11-23 00:45 local:**
- The second deletion at 00:41 was approved by Tony's click on Approve. The first request timed out without approval, which is correct. The earlier 00:24 deletion was a voice approval from a grunt, which the fix addresses.
- Added approval audit logging: `sidecar/approvals.py` logs every open, heard transcript (with its keyword decision), approval, decline and expiry with how it was answered. The sidecar writes it to `~/Library/Logs/com.tonyseneadza.rigel/approvals.log` (set up in `sidecar/app.py`). Verified with a temp file. Clicks are logged by the answer endpoint path, not yet checked live.
- Retry cap decided by Tony (00:55): three empty listens in total, then "click to answer". Changed `MAX_RELISTENS` from 3 to 2 in `desktop/src/App.jsx` (the first listen plus two re-listens). NOT tested: `vite build` and Vitest need the Mac.
- Log tip: the Python sidecar is not started by the Tauri app, so the approval audit file is the only place its decisions show up.

**Next steps:**
1. Review `git diff` on `fix/voice-approval-noise`, then run the sidecar suite on the Mac.
2. Retest with the TV muted. Create a disposable file, then ask for its deletion. Say nothing, or say "no" to decline. Expect follow-up questions, no approval, and the file kept. Watch for the bars and "click to answer", and note the result in this file.
3. Decide with Tony on gap 1 before anyone relies on voice approvals for deletes.

## ToolBox follow-up fixes + PR (2026-11-22)

**Branch:** `feature/rigel-view-screens-p2` (pushed) · **Draft PR:** https://github.com/tseneadza/rigel/pull/2 (persona + View Screens P1/P2 + these fixes; review before merging)

Found by testing "use ToolBox to delete scratch.txt in my rigel folder" in the native app:
- `a217a87` Guessed paths: every brain (including Claude Sonnet 5) targeted `~/rigel-files/` (Rigel's sandbox, seen in chat history). Fixed: `places_note()` in `tool_brain.py` (home, `~/Codehome/rigel`, sandbox), find-before-acting rule, `_missing_target` guard (no delete/move/rename for a path that doesn't exist), reply guard against "widen the allowed roots", honest reply when an outcome is repeated from history without a tool call. Tests: `sidecar/tests/test_paths.py`.
- `f3ba2fb` Rigel heard itself: a click-approved card left listen-once recording; it captured Rigel's reply. Fixed: `voice_cancel_listen_once`, drop a recording when TTS starts, transcripts carry `listen_once`, stray ones dropped.
- `dc666ae` Listening indicator: the card's bars follow the real `recording` state; after a stray sound it listens again up to 3 times, then shows "click to answer". **Not yet verified live.**

Verified live (Rigel.log): click approve and decline, spoken "Yes, approved.", click during the question (listen cancelled before it starts), click while recording (`recording dropped (listen-once cancelled)`), right file found and deleted.

Gates: 81 pytest tests, 9 Vitest tests, Vite build, and `cargo check` all clean.

Next session, start here:
1. Verify `dc666ae` with the mic. When a card appears, the bars should show only after Rigel stops speaking. Make a small sound and stay quiet: it should listen again, and after 3 empty tries show "click to answer".
2. Brain setting: Tony's saved brain is Ollama `dutchit/minimax-h3-prompt-enhancer` (a prompt rewriter, not a tool-use model; it runs no tools). Recommend Claude (key in the Keychain as `rigel-anthropic-key`).
3. Rigel's Claude model list is outdated (`claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5`); the key can reach Opus 5.5, Sonnet 5.5, Haiku 5.5 and Fable 5.2.
4. Review and merge PR #2; then continue View Screens (open P2 items below).
5. Noise floor: the voice log often shows `noise_floor=0.00000` (seen 2026-11-22 before the restart), so the speech threshold sits at its 0.003 floor and room noise ends a listen early. Worth a look with voice-pipeline-integrity.

---

## P2 checkpoint: sidecar + history (2026-11-20)

Done (not committed yet; branch `feature/rigel-view-screens-p2`):
- `sidecar/db.py`: `conversations` table; `turns.conversation_id` added with a backfill into one default conversation; backup before the first ALTER when turns exist; helpers `start_new_conversation`, `active_conversation_id`, `list_conversations`, `conversation_turns`, `conversation_history`.
- `sidecar/app.py`: `GET/POST /api/rigel/settings/mic-wake-word` (`{enabled}` under key `mic_wake_word_enabled`, default on); `GET /api/rigel/conversations`; `POST /api/rigel/conversations/new`; `GET /api/rigel/conversations/{id}/turns`. `/chat` now passes the active conversation's earlier turns to the brain.
- History to the model (Tony's answer 1, 2026-11-20): `history` threaded through `brain.respond_with_tools`, `tool_brain.respond` (Claude and Ollama loops), and `llm_providers.claude_respond` / `ollama_respond` via `with_history`.
- `desktop/src/api.js`: client functions for mute and conversations.
- `docs/mockups/mockup-v10-new-chat.html` copied from the vault (approved).

Tests: `sidecar/tests/test_db_conversations.py`, 6 tests pass when run with a stub pytest import in the Linux VM. Pytest itself, and the LLM paths, have NOT run; FastAPI and anthropic are not installed in the VM. Run `.venv/bin/python -m pytest` on the Mac.

Not done yet:
- Desktop UI BUILT (not run): `components/ConversationControls.jsx` (mute with slash, "+" New Chat, History), `components/HistoryPanel.jsx` (read-only past chats), wired into `App.jsx`, styles appended to `styles.css`, tests in `src/__tests__/ConversationControls.test.jsx`. The Vite build and vitest could NOT run in the Linux VM (node_modules from the Mac; rollup native binary missing). Run `npx vite build` and `npm test` on the Mac.
- Rust mute BUILT (not compiled): `voice/mod.rs` `WAKE_WORD_MUTED` flag + `voice_set_wake_word_muted` command + unit test; `voice/listener.rs` skips wake-word matching when muted, after the listen-once path so approvals still work; `lib.rs` registers the command; `src/voice.js` `setWakeWordMuted`; App syncs it on launch and on toggle. Run `cargo test` in `desktop/src-tauri` on the Mac (no cargo in the Linux VM). Known gap: a recording already started before muting still finishes and is sent.
- Gates on the Mac: `npx vite build`, `npm test`, pytest.
- Commit. Git lock files from an earlier commit still need the delete approval.

## P2 ready to cook (2026-11-18)

- Spec approved: `.cheese/specs/p2-new-chat-mute.md` (status `approved`). New Chat mockup v10 approved by Tony; copy in the vault at `01 - Projects/Rigel/Mockups/mockup-v10-new-chat.html`. Decisions logged in the vault's decision log under 00 - Raw.
- Conversation storage: a `conversations` table. Voice-pipeline-integrity and intent-definition-integrity apply to mute.
- Branch `feature/rigel-view-screens-p2` created from `ad142d7`. Uncommitted work carried over: the Vitest setup, `docs/CONTINUATION.md`, `desktop/package*.json`, `desktop/vite.config.js`, and the `.cheese/` spec. Decide whether to commit these on P2 or on P1 first.
- `/cook` did not start: the Claude session that set this up has no `cook` skill registered. It is installed on the Mac at `~/.claude/skills/cook`, so run `/cook .cheese/specs/p2-new-chat-mute.md` from a Claude Code session on the Mac in `~/Codehome/rigel`. Outer loop: after each halt at round 6, run `/cook --resume <slug>`, up to 50 rounds total.

## Frontend tests: Vitest added (2026-11-18)

- Added Vitest 3 (needed for Vite 7; the AgenticOS setup uses Vitest 1, which targets Vite 5), jsdom 24, @testing-library/react 16, jest-dom 6, user-event 14. Same setup as AgenticOS `gui/desktop` otherwise.
- `desktop/vite.config.js` has a `test` block (jsdom, globals, `vitest.setup.js`). `npm test` runs `vitest run` in `desktop/`.
- First test: `src/__tests__/BrainChip.test.jsx` (6 tests): the `describeBrain` labels and the chip's checking, ready and unavailable states. All pass. `npx vite build` passes.
- Not committed. Commit when Tony asks.
- Still open for P2: New Chat mockup (none yet), then the P2 spec under `.cheese/specs/` and the outer-loop `/cook` run.

## /cook setup: outer loop, 50 rounds (2026-11-18)

- Decision: run `/cook` per phase with an outer loop capped at 50 Press rounds in total. Cook halts after 6 rounds (`halt: press-round-limit`), so each halt is followed by `/cook --resume <slug>` until the phase is green or the 50-round total is reached.
- The skill's own caps are unchanged. Per-finding correction cap: 2. Per-gate fix rounds: 2. Auto-mode Cure passes: 2.
- Done means all gates green, a clean `/age` review, and every PRD FR verified on the real path. The browser check against the approved mockup is a manual step.
- Not yet decided, needed before P2 starts: (1) a New Chat mockup (v8 covers mute only, M6); (2) adding Vitest for frontend tests (new dev dependency).
- Next: once both are answered, write `.cheese/specs/p2-new-chat-mute.md` with one acceptance criterion per FR, branch `feature/rigel-view-screens-p2` from `ad142d7`, then run the outer loop.

## P1 fix: docked orb placement (resolved)

- Added `positionCorner="docked"` (App.jsx passes it for non-chat views). CSS: `.rigel-orb[data-position="docked"]` at bottom 14px, right 18px. Brain chip stacked above it at `bottom: 190px` (M1 layout).
- Measured in the browser (Toolbox view): orb y 195–356, header ends at y 66, so no overlap. Chip y 155–180, above the orb. Hovering the orb shows the chip.
- `vite build` passes. Not committed.
- Still open: FR-31 (fallback state) and FR-32 (click chip → Settings) are deferred; M1 vs FR-9 (docked only for non-chat views) is still to confirm with Tony.
## P1 change: brain chip shows on orb hover (mockup v9 approved)

- `desktop/src/styles.css`: the brain chip is hidden (opacity 0, 0.2s fade) until `.rigel-orb` is hovered. Rule: `.stage:not(:has(.rigel-orb:hover)) .brain-chip`.
- `vite build` passes. In the browser, the chip showed on orb hover and hid when the pointer left (computed opacity 1 and 0).
- Still open: the docked orb sits at the top right, over the header (see the P1 verification note above). Layout fix needs Tony's OK.
- Not committed. Commit on `feature/rigel-view-screens` only when Tony asks.

## P1 verification (View Screens, feature/rigel-view-screens)

- Ran sidecar + Vite dev server on the Mac, checked http://localhost:1425/ in Chrome.
- Header view dropdown works: Agent Chat / Toolbox / Presentation. Switching shows the ViewArea placeholders. Console: no errors.
- Brain chip renders bottom-right with "Ollama · dutchit/minimax-h3-prompt-enhancer:latest · Local".
- BUG: docked orb (Toolbox, Presentation) sits at the top-right, overlapping the header. Cause: `.rigel-orb[data-position="bottom-right"]` uses `bottom: 160px`, which was tuned for the full-height resting layout. In docked mode `.stage` is ~277 px tall, so the offset lands at the top. Fix idea: a docked-specific bottom offset (about 14 px, aligned with the brain chip) and the chip stacked above the orb, per mockup M1. Needs Tony's OK on the layout before changing.
- Open: M1 shows the docked orb in Agent Chat, but FR-9 says docked only for non-chat views (P1 follows FR-9). FR-31 and FR-32 are not implemented.
- Verify: take a screenshot at 1140x581, select Toolbox, and check that `.rigel-orb` bottom edge is above the footer and not over the header.

## 2026-11-17: Persona + default voice

**Branch:** `claude/nifty-dirac-09rv78` · **Commit:** `329a41c` (not pushed)

### Done
- **Persona, first cut:** `sidecar/persona.md`. Colleague + mentor; mostly
  dry/witty with warmth, adaptive; challenges firmly until given a reason,
  then commits to Tony's call; wit off on errors and when Tony is
  frustrated; addresses him as Tony (default) / Boss (casual) / Sir
  (deadpan, approvals) / Sire (mock grandeur). Personality applies in
  conversation only; app handlers stay functional. Accepted as a first cut;
  refinements later.
- **Default voice:** Samantha + "warm" ffmpeg filter (`WARM_FILTER` in
  `desktop/src-tauri/src/voice/tts.rs`), chosen from
  `docs/mockups/voice/h2-warm.wav`. Falls back to plain `say` without
  ffmpeg. 12 unit tests + 2 live tests pass (speaks; interrupt stops audio).
  Documented in `docs/features/voice-pipeline.md`.

### Decided
- `persona.md` in the repo is the **master**; the Rigel second brain gets a
  **mirror**; the Settings window can **override** locally.
- Voice can't be an Ultron/James Spader imitation. Rigel's voice is an
  original one. Tony picked a female voice (Samantha, warm).

### Next up (in order)
1. **Wire persona into the sidecar:** load `sidecar/persona.md` in place of
   the hard-coded identity opening of `SYSTEM_PROMPT` in
   `sidecar/llm_providers.py`; keep the command-detection rules and
   `TOOLBOX_SYSTEM` (tool_brain.py) as separate blocks. Do NOT apply it to
   app-handler prompts (`sidecar/handlers/*.py`).
2. Mirror `persona.md` into the Rigel second brain.
3. Settings override for the persona (stored in Rigel's DB, file = default).
4. Settings toggle for the warm voice filter (currently always on, all voices).
5. Optional voice upgrade: download Ava (Premium) / Zoe (Premium) in
   System Settings → Accessibility → Spoken Content and re-sample with the
   warm chain.

### Loose ends
- Uncommitted on the branch, **not from this session:** `sidecar/brain.py`,
  `docs/features/app-handlers.md`, `docs/architecture/app-handlers.md`.
  Check what these are before committing anything else.
- Untracked voice samples in `docs/mockups/voice/` (only `h2-warm.wav` is
  committed); safe to delete.
- The `voice-pipeline-integrity` skill references files that don't exist in
  this repo (`stt_config.toml`, `rigel-voice-test` bin, `VOICE_CONFIG.md`);
  worth rewriting to match the real `src/voice/` layout.

