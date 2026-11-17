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
