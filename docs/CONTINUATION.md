# Rigel: Continuation

Read this first at the start of every Rigel session. Newest entry on top.

---

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

## P1 verification (View Screens, feature/rigel-view-screens)

- Ran sidecar + Vite dev server on the Mac, checked http://localhost:1425/ in Chrome.
- Header view dropdown works: Agent Chat / Toolbox / Presentation. Switching shows the ViewArea placeholders. Console: no errors.
- Brain chip renders bottom-right with "Ollama · dutchit/minimax-h3-prompt-enhancer:latest · Local".
- BUG: docked orb (Toolbox, Presentation) sits at the top-right, overlapping the header. Cause: `.rigel-orb[data-position="bottom-right"]` uses `bottom: 160px`, which was tuned for the full-height resting layout. In docked mode `.stage` is ~277 px tall, so the offset lands at the top. Fix idea: a docked-specific bottom offset (about 14 px, aligned with the brain chip) and the chip stacked above the orb, per mockup M1. Needs Tony's OK on the layout before changing.
- Open: M1 shows the docked orb in Agent Chat, but FR-9 says docked only for non-chat views (P1 follows FR-9). FR-31 and FR-32 are not implemented.
- Verify: take a screenshot at 1140x581, select Toolbox, and check that `.rigel-orb` bottom edge is above the footer and not over the header.

## P1 change: brain chip shows on orb hover (mockup v9 approved)

- `desktop/src/styles.css`: the brain chip is hidden (opacity 0, 0.2s fade) until `.rigel-orb` is hovered. Rule: `.stage:not(:has(.rigel-orb:hover)) .brain-chip`.
- `vite build` passes. In the browser, the chip showed on orb hover and hid when the pointer left (computed opacity 1 and 0).
- Still open: the docked orb sits at the top right, over the header (see the P1 verification note above). Layout fix needs Tony's OK.
- Not committed. Commit on `feature/rigel-view-screens` only when Tony asks.

## P1 fix: docked orb placement (resolved)

- Added `positionCorner="docked"` (App.jsx passes it for non-chat views). CSS: `.rigel-orb[data-position="docked"]` at bottom 14px, right 18px. Brain chip stacked above it at `bottom: 190px` (M1 layout).
- Measured in the browser (Toolbox view): orb y 195–356, header ends at y 66, so no overlap. Chip y 155–180, above the orb. Hovering the orb shows the chip.
- `vite build` passes. Not committed.
- Still open: FR-31 (fallback state) and FR-32 (click chip → Settings) are deferred; M1 vs FR-9 (docked only for non-chat views) is still to confirm with Tony.
