---
name: capture-to-raw
description: >
  Rule for creating NEW notes in Tony's Obsidian vaults: every new ad-hoc note
  goes into that vault's `00 - Raw/` and stays there until it is processed. For
  Rigel work the vault is `~/tonys-neural-vault/Rigel` (Brain2 is deprecated).
  Use whenever the user asks to "document", "log", "capture", "jot down", "write
  up", or "add to the brain" a bug, feature idea, finding, decision, mockup
  discussion, or session summary and no more specific skill defines the
  destination. Do NOT write the note straight into `01 - Projects/`,
  `07 - Claude Sessions/`, etc., and do NOT process it in the same turn.
---

# Capture to Raw

New notes are staged in the vault's `00 - Raw/`. Classifying, templating, wikilinking
and filing into the final folder are a **separate, later step**. Tony's standing rule
(confirmed 2026-11-18): new notes go to Raw until they are processed.

## Which vault

- **Rigel work** (Rigel app, ToolBox, anything under the Rigel umbrella):
  `/Users/tonyseneadza/tonys-neural-vault/Rigel/00 - Raw/`
- **Other vaults** under `~/tonys-neural-vault/` (Fritz, OSA): that vault's own
  `00 - Raw/` if it exists. If it does not, ask before creating one.
- **`~/Brain2` is deprecated.** Use it only if Tony says so. Its `com.brain2.process-raw`
  launchd job (09:00 and 18:00) covers `~/Brain2` only.

## The rule

1. **Destination:** `<vault>/00 - Raw/<YYYY-MM-DD> - <Title>.md`. Never a project or session folder.
2. **Stop there.** Do not process, move, or archive the note in the same turn unless
   the user explicitly asks in that same request.
3. **Tell the user** the exact path and that it is waiting in Raw. Say plainly that,
   as far as I found on 2026-11-18, nothing processes the Rigel vault's Raw on a
   schedule: it is filed when Tony asks (for example "process raw notes" or a steward
   run in that vault).

## What the raw note looks like (Rigel vault precedent)

Frontmatter, matching the notes already waiting in the Rigel vault's Raw:

```
---
created: YYYY-MM-DD
type: <reference | session-log | prd | mockup | feature-idea | ...>
title: <Title>
status: ready
ready_to_process: true
project: Rigel
related: "[[Existing Note]]"
source: "<where the facts came from: repo path and commit, session, file>"
---
```

Then an H1, then a `> Processing hint:` line saying where it should be filed and as
what (for example "file as `01 - Projects/Rigel/<Title>.md` (type Reference)").
If the note will be linked from an existing note under a specific name, say so in
the hint so the filed note gets that name.

Write what was said and decided in plain structure (summary, decisions, open items).
Preserve Tony's own words where they matter.

## Mockups

A mockup shown during Rigel work must be captured, not left in chat or an untracked folder.
- Save the HTML to `01 - Projects/Rigel/Mockups/` (an attachment, saved directly, keeping the repo filename).
- Update `Rigel Mockups.md` in place (an existing note) with a row: what it shows, date,
  commit or location, status.
- Log Tony's answer and the decisions the same day: append to `Rigel Mockup Decision Log.md`
  if it has been filed; if it is still in Raw, append to the Raw copy.

## Facts about code must be verified against committed code

Use `git show HEAD:<path>` / `git log` in the repo (Rigel: `~/Codehome/rigel`,
ToolBox: `~/Codehome/ToolBox`) and confirm `git status` shows the file unmodified.
Record the commit and branch, say whether it is on `main`, and say what is verified on
real hardware versus only mocked or built. A note that says "bug" or "not implemented" can
go stale within a day; if the repo already has the fix, say so.

## What this rule does NOT cover

- **Editing an existing note in place** (progress entries, status changes, corrected facts).
- **Specialized skills keep their own destinations** (`process-projects`,
  `research-learning-notes`, `save-session`).
- **`Templates/`, `.obsidian/`, and auto-generated files** (`index.md`, `_index.md`, `_log.md`,
  `VAULT-INDEX.md`).
- **An explicit destination from Tony wins.** Mention that it skipped Raw.

## Checklist

- [ ] Right vault (Rigel work → the Rigel vault)
- [ ] Path is `<vault>/00 - Raw/<date> - <Title>.md`, with the frontmatter above and a processing hint
- [ ] Code claims checked against committed code, commit and branch noted
- [ ] Any mockup saved to `Mockups/` and logged
- [ ] Nothing processed, moved, or archived
- [ ] User told where the note is waiting
