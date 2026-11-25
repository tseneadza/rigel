# Rigel: Continuation

Read this first at the start of every Rigel session. Newest entry on top.

---

## Toolbox view M2: Rigel and other agent pinned in 2D (v8.3) BUILT and verified (2026-11-25, 03:05)

**Branch:** `feature/rigel-toolbox-view` · **Not committed.**

- Tony: wants the Rigel / other-agent boxes back; chose "pinned at the edge", 2D only (3D stays servers only: "That is the look I requested"). Mockup v8.3 approved ("Yes, build it"); same file `docs/mockups/toolbox-view-m2-v8-layout.html`.
- BUILT: `ToolBoxMap.jsx` exports `PINNED_AGENTS` and `agentLinkEnd(index, zoom)`. The boxes sit at x 30, y 200 / 340 in the 1000×600 viewBox and don't spin, tilt or zoom. Their links are drawn first (under everything) and end at the hub edge for the current zoom; the boxes are drawn last (on top). `styles.css`: `.tb-agent` and `.tb-agent--other` have a solid dark fill (#0a1428) so they stay readable over the rings.
- Tests: 4 new (boxes present at fixed positions, drawn after the servers, still after zoom with links on the hub edge, absent in 3D). `npx vitest run`: 5 files, 60 tests pass. `vite build` passes.
- VERIFIED IN THE TAURI APP: `.verify-screenshots/v83-a-2d.png` (1.0×) and `v83-b-zoom.png` (2.1×). Rigel window confirmed frontmost by `osascript` before input; an earlier attempt hit the Claude app instead (window order), so check frontmost first.
- The open question from the entry below (bring the agents back) is answered.

## Toolbox view M2: 2D spin, tilt, zoom + layout fix BUILT and verified in the app (2026-11-25, 02:55)

**Branch:** `feature/rigel-toolbox-view` · **Not committed.** Commit when Tony asks; push from the Mac.

- Tony approved mockup v8.2 (`docs/mockups/toolbox-view-m2-v8-layout.html`): "Approve, build it".
- BUILT (uncommitted):
  - `desktop/src/toolboxFlat.js` (new): 2D geometry. `ringAngles`, `flatPoint` (spin, tilt squashes vertically, zoom scales around the hub), `clampFlatTilt` (20° to 90°, default 90° = straight down), `clampFlatZoom` / `flatWheelZoom` (0.5× to 2.1×, scroll down zooms out, as in 3D).
  - `desktop/src/components/ToolBoxMap.jsx`: 2D is now a `FlatMap` that turns on its own (`IDLE_SPIN`, pauses while dragging), drag left/right spins, drag up/down tilts, the wheel zooms. Rings are ellipses; labels stay upright. Layout is a grid: map column (map, then `.tb-bar` with hint and readout) and the Servers column. `placeOnRings` removed (replaced by `ringAngles`). **The Rigel and "other agent" boxes are gone from 2D**, matching the approved v8.2 mockup (they would collide with the zoomed rings). Exports `HINT_2D`, `HINT_3D`, `flatReadout`.
  - `desktop/src/components/ToolBoxScene.jsx`: no more floating hint/readout; it renders the map box plus the same `.tb-bar` (readout via ref). Takes a `hint` prop.
  - `desktop/src/styles.css`: `.tb-map-wrap` grid, `.tb-map-col`, `.tb-map` (62vh, no text selection on drag), `.tb-bar*`; `.tb-side` no longer absolute; `.tb-scene` fills `.tb-map`; old `.tb-scene-readout` / `.tb-scene-hint` removed.
  - Tests: `src/__tests__/toolboxFlat.test.js` (9, new); `ToolBoxMap.test.jsx` gets 6 new tests (bar under the map, Servers in its own column, idle spin, drag tilt, wheel zoom limits, 3D bar). The Rigel-box assertion was replaced. jsdom has no PointerEvent, so the drag test stubs one on MouseEvent.
- VERIFIED: `npx vitest run`: 5 files, 56 tests pass (connected Linux VM). `npx vite build --outDir /tmp/<new dir>` passes (bundle 759 kB, the same three.js size warning).
- VERIFIED IN THE TAURI APP (screenshots `.verify-screenshots/v82-a` to `v82-d`): 2D shows 14 servers with the Servers panel beside the map and the bar under it, no overlaps; idle spin moved the map within 4 s; a real mouse drag down and scroll gave "2D · Tilt 60° · Zoom 1.7×" with oval rings; 3D renders with its hint and readout in the bar, and agentic-dev, gmail and claude-code-usage are no longer covered.
- NOT VERIFIED: the remembered 2D/3D choice after reload; the WebGL fallback in the app; other window sizes. Label crowding at 0.5× zoom is still open. 2D tilt/zoom reset when switching modes (not persisted; not asked for).
- (answered 03:05: yes, pinned at the left edge in 2D; see the entry above)
- Still to do: vault copies of mockups v4 to v8 and decision-log entries; delete `.verify-screenshots/` (untracked, don't commit).

## Toolbox view M2: mockup v8 / v8.1, layout approved (2026-11-25, 02:50)

- New mockup `docs/mockups/toolbox-view-m2-v8-layout.html` (uncommitted). It supersedes v7 for 2D. 2D is the flat SVG map; it **turns on its own** (idle spin, same rate as 3D, pauses while dragging), and drag left/right spins it. 3D is unchanged from v5. three.js now loads only when 3D is opened, so 2D works where the CDN is blocked.
- Tony's answers this session:
  - **Layout fix APPROVED:** the Servers panel gets its own column beside the map; the hint and tilt/zoom readout go in a bar under the map. Nothing sits on the map.
  - **Defaults CONFIRMED:** a down server is a red node with its error line; cold is a grey node; no pulse on tool use in v1; 3D shows servers only.
  - **2D motion:** "doesn't rotate" meant "turn on its own" (not drag). Added to v8.1.
  - **Auto-spin approved** (02:46): "The auto-spin is exactly what I want and what it used to be!"
  - Tony then asked for **tilt and resize in 2D too**. Built in mockup v8.2 (same file): 2D stays a flat SVG (no shaded spheres); drag up or down tilts it from 90° (straight down, the default) to 20°, so the rings become ovals and the labels stay upright; the scroll wheel zooms 0.5× to 2.1× (same direction as 3D); readout "2D · Tilt N° · Zoom N×". Verified in headless Chrome with unpkg blocked: tilt 90° to 40° to 60°, zoom clamps at 0.5× and 2.1×, no errors. **v8.2 is awaiting Tony's approval.**
- Debug note: the first v8 drew nothing in the Claude preview panel because the panel blocks the unpkg three.js import, which broke the whole module. Reproduced in headless Chrome by blocking unpkg; fixed by the lazy 3D import. The real app bundles three, so this only affected the mockup.
- VERIFIED (headless Chrome in the cloud workspace, unpkg blocked and unblocked): 2D draws 14 nodes; idle spin 4° to 31° in 4 s; it holds still while the mouse is held; a drag spins it; 3D renders when three loads; the fallback "3D unavailable here, showing 2D." shows when it doesn't. Also seen on Tony's screen: his preview showed "2D · flat · 342°".
- NOT DONE: no app code changed this session. Vault copy of the mockups and the decision log are still to do.
- Next: (1) get Tony's approval of v8.2; (2) build 2D idle spin, drag spin, tilt and zoom in `ToolBoxMap.jsx` plus tests; (3) build the layout fix (grid: map column with a bar under it, Servers column); (4) verify in the Tauri app with screenshots; (5) check the remembered 2D/3D choice and the WebGL fallback in the app.

## Toolbox view M2: handoff to a new session (2026-11-25, 02:35)

**Read `docs/handoff-toolbox-view-m2.md` first.** It has the full state, the mockup decisions, the verified list, and the next steps.

- Branch `feature/rigel-toolbox-view`; everything since `1b5621b` is uncommitted. Commit only when Tony asks; push from the Mac.
- Approved: 3D look (v4), 3D tilt and zoom (v5). Awaiting approval: 2D flat spin (v7). Superseded: v6.
- Open: the Servers panel and hint/readout overlap in the app; label crowding when zoomed out; the defaults for down servers and tool-use pulse.
- Verified in the Tauri app: 2D flat map, 3D render, tilt, zoom, spin, and the clipping fix. Not verified: 2D spin (not built yet), the remembered choice after reload, and the WebGL fallback in the app.

## Toolbox view M2: 3D tilt and zoom (2026-11-25, 02:20)

**Branch:** `feature/rigel-toolbox-view` · **Not committed.** Commit when Tony asks.

- Tony approved the tilt and zoom mockup: "Use this mockup. This is more like what I expect." Saved: `docs/mockups/toolbox-view-m2-v5-tilt.html`.
- Decisions (Tony): drag up or down tilts (flat about 85° to edge-on about 5°; up tilts toward flat); drag left or right spins; scroll wheel zooms (about 0.5× whole map to about 2.1× close up); readout bottom right shows tilt and zoom; default tilt 27°. No reset button.
- BUILT (uncommitted): `desktop/src/toolboxScene.js` (tilt and zoom limits, camera position, wheel zoom); `desktop/src/components/ToolBoxScene.jsx` (the orbit stays flat, the camera moves; drag and wheel handlers; readout and hint); `desktop/src/styles.css` (`.tb-scene-readout`, `.tb-scene-hint`); `desktop/src/__tests__/toolboxScene.test.js` (7 tests).
- VERIFIED: `npx vitest run` in `desktop/`: 4 files, 41 tests pass (Linux VM). `npx vite build --outDir /tmp/rigel-build-check` passes.
- FIXED: rollup's Linux binary was missing from `node_modules` (only the macOS binary was installed). `npm install` restored it. The lockfile was fine.
- NOT VERIFIED: tilt, zoom and the readout in a real browser with WebGL. Test on the Mac with `npm run dev`.
- Vault copy of the v4 and v5 mockups and the decision log are still to do.

## Toolbox view M2: 3D rebuilt with WebGL (three.js) (2026-11-25)

**Branch:** `feature/rigel-toolbox-view` · **Not committed.** Commit when Tony asks.

- Tony approved the 3D look: "That looks amazing." Mockup saved: `docs/mockups/toolbox-view-m2-v4-webgl.html` (uncommitted; the vault copy is still to do, as the vault is not reachable from this session).
- Tony chose WebGL (three.js) over CSS 3D. The old SVG orbit (`orbitPoint`, `orbitNodes`, `depthScale`, `TILT`, `PERSPECTIVE`) is removed; it never looked three-dimensional.
- BUILT (uncommitted):
  - `desktop/package.json` + `package-lock.json`: `three` ^0.170.0 (lock diff is only the three entries).
  - `desktop/src/toolboxView.js`: `supports3D()` now checks for a WebGL context (was CSS 3D); `ringFor` moved here, shared by both views.
  - `desktop/src/toolboxScene.js` (new): `scenePositions(rows)`, ring radii, tilt.
  - `desktop/src/components/ToolBoxScene.jsx` (new): three.js scene. One renderer per mount; nodes rebuilt only when server data or hub state changes; labels are HTML over the canvas; drag to spin; idle spin; disposes on unmount; calls `onFail` if WebGL won't start.
  - `desktop/src/components/ToolBoxMap.jsx`: 3D uses the scene; 2D SVG is unchanged. A WebGL failure shows "3D unavailable here, showing 2D.".
  - `desktop/src/styles.css`: `.tb-scene*` rules.
  - `desktop/src/__tests__/ToolBoxMap.test.jsx`: SVG orbit tests replaced. New: shared scene positions, WebGL check, 3D fallback, 3D draws labels (renderer stubbed via `vi.mock("three")`), 2D never builds the scene.
- VERIFIED: `npx vitest run` in `desktop/`: 3 files, 34 tests pass (run in the connected Linux VM, not on the Mac host). `npx vite build --outDir /tmp/rigel-build-check` passes.
- NOT VERIFIED: the 3D scene in a real browser/WebGL context; the 2D view in the running app with the 14 live servers; the 2D/3D toggle live. jsdom has no WebGL, so the scene is only proven to mount with a stubbed renderer.
- NOTE: `vite build` into `desktop/dist` fails here (cannot delete old files without delete permission). Use `--outDir` outside the repo, or build on the Mac.
- NOTE: the JS bundle is now ~757 kB (three.js). Vite warns above 500 kB. Consider lazy-loading `ToolBoxScene` (`React.lazy`) later.
- Decisions taken (Tony did not confirm them): 3D shows servers only (no Rigel / other-agent boxes, as in mockup v4); 2D stays the flat SVG (the choice in the earlier question was not answered; default kept); down server = red node + error line; cold = neutral grey; no pulse on tool use in v1.
- Next steps: (1) run `npm install` and `npm test` on the Mac; (2) run `npm run dev`, open the Toolbox view, and check 3D in a real window (drag, toggle, labels, error line for `image-tools`, fallback); (3) decide whether Rigel and the other agent should appear in 3D; (4) save the vault mockup copy and a decision-log entry; (5) commit and push from the Mac when Tony asks.

## Toolbox view M2: built, NOT verified, live data blocked (2026-11-23 03:40)

**Branch:** `feature/rigel-toolbox-view` (from `ec50782`, the View Screens P2 branch; NOT from the speaker-verification HEAD) · **Not committed.** Commit when Tony asks.

- Mockup v2 approved by Tony: `docs/mockups/toolbox-view-m2-v2.html` (uncommitted). Earlier v1: `docs/mockups/toolbox-view-m2-v1.html`.
- Decisions (Tony): ToolBox at the centre of the map, Rigel and other agents at the edge; 2D | 3D toggle in the header; 2D opens first and the choice is remembered (localStorage `rigel.toolboxView`); 3D falls back to 2D with "3D unavailable here, showing 2D." when CSS 3D transforms are missing; 3D style is orbit with drag to rotate; read-only; current state only.
- Defaults I took, not yet confirmed by Tony: a down server stays a red node with its error line; no pulse on tool use in v1.
- BUILT (uncommitted): `desktop/src/toolboxView.js` (stateTone, supports3D, readStoredMode, storeMode, resolveMode); `desktop/src/components/ToolBoxMap.jsx`; `desktop/src/components/ToolBoxModeToggle.jsx`; `ViewArea.jsx` Toolbox branch now renders the map; `App.jsx` holds the mode and shows the toggle when the Toolbox view is active; `styles.css` `.tb-*` rules; `src/__tests__/ToolBoxMap.test.jsx` (state tones, mode fallback, remembered mode, map labels, error line, empty state, toggle).
- VERIFIED ON MAC (2026-11-23 03:21): `npm test` 19 of 19 pass (3 files); `npx vite build` passes. One test first failed on Node's built-in localStorage; fixed with an in-memory stub in `ToolBoxMap.test.jsx`.
- NOT YET VERIFIED LIVE: the map in the running app (2D/3D toggle, fallback) and the sidecar tests on the Mac (`./.venv/bin/python -m pytest -q sidecar/tests`).
- (Earlier note, superseded for tests:) the sandbox is Linux and `node_modules` has macOS binaries, so Vitest and `vite build` could not run here. Nothing in the desktop code has been run. Run `npm test` and `npx vite build` in `desktop/` on the Mac.
- 2026-11-23 03:30 DATA IN: Tony's ToolBox `/status` sample: 14 servers; each has `tools`, `state`, `last_error`. Every server was `cold` (ToolBox's idle label, starts on demand) with no errors. Tony's decision: show `cold` as its own neutral grey label, not red; red only for an error.
- BUILT: `sidecar/toolbox_client.py` `server_rows()` passes ToolBox's labels through and maps `last_error` to `error`; `status()` returns `server_rows`. Tests: `sidecar/tests/test_toolbox_status.py` (4). Map shows any server's error line; `cold` test added to `ToolBoxMap.test.jsx`.
- Sidecar tests on Mac before this change: 81 passed. Desktop: 19 passed.
- 2026-11-23 03:40 Tony's layout choice: two rings by state (running inner, cold and others outer). Mockup v3 saved and verified on disk: `docs/mockups/toolbox-view-m2-v3.html` (real 14 server names and counts, 132 tools; the running states and the one error are illustrative). v3 needs Tony's approval before the map code changes.
- 2026-11-23 03:45 v3 approved by Tony ("I like!"). Built via /cook by hand (the cook scripts need the Mac environment): spec `.cheese/specs/m2-toolbox-view.md` (approved); handoff `.cheese/cook/m2-toolbox-view.md` (next: age). Code: `ToolBoxMap.jsx` now places running/starting/stopping on the inner ring, others outer; side panel summary; hover title per server. Tests: ring and summary tests added.
- VERIFIED ON MAC (2026-11-23 03:33): `npm test` 25 of 25 pass (3 files); `npx vite build` passes; sidecar `pytest sidecar/tests` 85 passed.
- NOT YET: a browser check of the two-ring map with the 14 live servers (`npm run dev`, `http://localhost:1425/`, Toolbox view, 2D and 3D). Not committed.
- Tests on Mac after the adapter: sidecar and desktop both passed (Tony, 03:27).
- (layout issue now decided, see above) OPEN LAYOUT ISSUE: 14 servers on the one 2D ring will overlap their labels. The mockup had 7. Needs a layout decision (two rings, a list beside the map, or a scroll) before the 2D view is final.
- (superseded) BLOCKED: live server data. `App.jsx` reads `toolboxStatus.server_rows`, which the sidecar does not send yet. `sidecar/toolbox_client.py` `status()` only keeps the server count and total tools. Needed: a sample of ToolBox `/status` (`curl -s http://127.0.0.1:8795/status` on the Mac, redacted), then write the adapter that turns it into `server_rows: [{name, state, tools, error?}]`. The ToolBox source folder (`~/Codehome/ToolBox`) is not readable from this session (access denied by the auto-mode classifier).
- Git: this session needed delete permission on `/Users/tonyseneadza/Codehome/rigel` (granted by Tony, 2026-11-23 03:35). Stale lock files from earlier failed commands remain under `.git/` (`stale-*`); they can be deleted now. A stash from the speaker-verification branch was dropped after its checkpoint was reapplied here.
- Not done: vault copy of the mockups and a decision-log entry (`~/tonys-neural-vault/Rigel` is not reachable from this session).
- Next steps: (1) Tony runs `npm test` and `npx vite build` on the Mac; (2) Tony supplies the `/status` sample; (3) write the `server_rows` adapter and its sidecar test; (4) confirm the two defaults above; (5) verify on the Mac with ToolBox running and one server stopped, toggle 2D/3D, and force the 3D fallback; (6) commit when Tony asks.

---

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

