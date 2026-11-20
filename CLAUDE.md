# Rigel — agent instructions

Rigel is a voice-controlled desktop assistant: a Tauri + React/Vite desktop app (`desktop/`) and a Python
sidecar (`sidecar/`). Read `docs/CONTINUATION.md` **before doing any work**; it is the handoff from the last session.

## Project home

- Rigel's Obsidian brain is the vault at `~/tonys-neural-vault/Rigel`: project notes in `01 - Projects/Rigel/`
  (listed in `_index.md`), session logs in `07 - Claude Sessions/`. **New notes go to `00 - Raw/` until they are
  processed.** (`capture-to-raw` skill. Nothing processes this vault's Raw on a schedule, so say where you left a note.) Don't use Brain2 or the other vaults. Check vault notes against the repo before trusting them.
- The persona master is `sidecar/persona.md`; the vault holds a mirror. Edit the repo file first.

## Working rules

1. **Mockup before code.** For any new feature or UI, show Tony a mockup or design and get approval before
   implementing it. Then save the mockup (the HTML file, not just a chat message, and not an untracked folder like
   `Claude outputs/`) to the vault's `01 - Projects/Rigel/Mockups/`, add it to `Rigel Mockups.md`, and log Tony's
   answer and the decisions in `Rigel Mockup Decision Log.md` the same day.
2. **Interview on ambiguity.** If an idea is unclear, ask. Don't guess at scope.
3. **Evidence over theory when debugging.** Follow the `debug-discipline` skill
   (`~/.claude/skills/debug-discipline/`). Reproduce on the real failing path, and only call something fixed after
   re-reproducing the fix on that same path.
4. **Branch for development.** When coding starts, create a new git branch (for example `feature/<name>`) and
   work there, not on `main`. Commit when Tony asks.
5. **Verify deploys.** After writing a file to Tony's machine, check the file on disk (size or a grep). Don't trust
   a "written" message.
6. **Checkpoint.** Before stopping, update `docs/CONTINUATION.md` (newest entry on top): what was done, what is in
   progress, exact next steps, and how to verify. Never leave the repo broken.
7. **Use subagents** when work splits into independent parts.
8. **Say what is verified.** Record what was checked on the real path (or on the Mac) and what was only mocked or
   built.
