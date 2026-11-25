# Handoff: Toolbox view (M2), 2D flat spin, 3D tilt and zoom

Read this first in the next session. It is the full state of the Toolbox view work as of 2026-11-25 02:35 (Eastern). Then read `docs/CONTINUATION.md` (newest entry on top) and `CLAUDE.md`.

## Where things stand

- **Branch:** `feature/rigel-toolbox-view`. Last commit `1b5621b`. **Everything below is uncommitted.** Commit only when Tony asks, and push from the Mac (`git push -u origin feature/rigel-toolbox-view`). Commit messages end with the two attribution lines from the session rules.
- **Goal:** a read-only live map of ToolBox and its servers (PRD M2 in `prd/rigel-view-screens.md`). ToolBox is the hub. Servers on two rings by state: running, starting and stopping on the inner ring; cold and other states on the outer ring. 2D | 3D toggle in the header; 2D is the default and the choice is remembered (`localStorage` key `rigel.toolboxView`).
- **Working in the Tauri app:** verified this session (see "Verified" below).

## Mockups (Tony's decisions)

| File (in `docs/mockups/`) | Status |
|---|---|
| `toolbox-view-m2-v1.html` | Superseded (Rigel in centre) |
| `toolbox-view-m2-v2.html` | Approved: ToolBox centre, 2D/3D toggle |
| `toolbox-view-m2-v3.html` | Approved: two rings by state (the 2D layout) |
| `toolbox-view-m2-v4-webgl.html` | Approved look for 3D: "That looks amazing." (no tilt control in v4) |
| `toolbox-view-m2-v5-tilt.html` | **Approved** for 3D: drag up/down tilts (about 85° flat to 5° edge-on, default 27°), scroll zooms (about 0.5× to 2.1×), readout bottom right |
| `toolbox-view-m2-v6-2d-spin.html` | Superseded: 2D was still 3D at 85° tilt. Tony: "Still looks 3d" |
| `toolbox-view-m2-v7-2d-flat.html` | **Awaiting Tony's approval.** 2D is a flat SVG (the v3 look), drag left or right spins it in-plane, no tilt, no zoom. 3D unchanged from v5 |

Tony's answers to the 2D questions: rotation = "Drag to spin" (flat, no tilt). He wants 2D to rotate. The phrase "as it does in the Toolbox app" was never resolved; the answer was "Drag to spin".

## Decisions still open

1. Approve v7 (2D flat spin). Build only after approval (CLAUDE.md: mockup before code).
2. **Overlaps** (seen in the app at the default size): the Servers side panel covers the agentic-dev label; the hint text and the tilt readout cover the gmail and claude-code-usage labels. Proposed fix, not yet approved: move the hint and readout into a bar below the scene; move the Servers panel beside the map, not over it. Mock up before building.
3. Label crowding when zoomed out (about 0.5×): agentic-dev, ai-image-detector and claude-code-usage overlap. Decide later whether labels hide when crowded.
4. Defaults not yet confirmed by Tony: a down server is a red node with its error line; cold is a neutral grey node; no pulse on tool use in v1; 3D shows servers only (no Rigel or other-agent boxes, as in v4 to v7).
5. Vault copies of the mockups and a decision-log entry in `~/tonys-neural-vault/Rigel` are still to do. The vault is not reachable from the Claude session; it may need the Mac shell.

## Code state (uncommitted, branch `feature/rigel-toolbox-view`)

- `desktop/package.json`, `desktop/package-lock.json`: `three` ^0.170.0 added. Lock diff is only the three entries (the libc lines were restored to HEAD).
- `desktop/src/toolboxView.js`: `supports3D()` checks for a WebGL context (was CSS 3D). `ringFor` lives here (shared).
- `desktop/src/toolboxScene.js` (new): `scenePositions`, ring radii (2.2 inner, 3.6 outer), tilt and zoom limits (`DEFAULT_TILT` 27°, `MIN_TILT` 5°, `MAX_TILT` 85°, `DEFAULT_DISTANCE` 9.5, `MIN_DISTANCE` 4.5, `MAX_DISTANCE` 20), `clampElevation`, `clampDistance`, `wheelZoom`, `cameraPosition`, `zoomFactor`, `toDegrees`.
- `desktop/src/components/ToolBoxScene.jsx` (new): three.js scene. One renderer per mount; rebuilds nodes only when server data or hub state changes; HTML labels over the canvas; drag left/right spins, drag up/down tilts (up = flatter); wheel zooms; readout and hint; disposes on unmount; calls `onFail` if WebGL won't start (parent then shows 2D with "3D unavailable here, showing 2D.").
- `desktop/src/components/ToolBoxMap.jsx`: 3D uses the scene; 2D is the flat SVG (unchanged from before). Re-exports `ringFor`. Old SVG orbit code (`orbitPoint`, `orbitNodes`, `TILT`, `PERSPECTIVE`) removed.
- `desktop/src/styles.css`: `.tb-scene` height is now `clamp(420px, 62vh, 820px)` (was a fixed aspect ratio; that clipped the bottom nodes). Also `.tb-scene-readout`, `.tb-scene-hint`, `.tb-scene-title/sub/err`, `.tb-scene-label--bad`.
- `desktop/src/__tests__/ToolBoxMap.test.jsx`: SVG-orbit tests replaced. Tests for shared scene positions, WebGL check, 3D fallback, 3D draws labels (renderer stubbed with `vi.mock("three")`), 2D never builds the scene.
- `desktop/src/__tests__/toolboxScene.test.js` (new): 7 tests for tilt, camera and zoom limits.
- `docs/CONTINUATION.md`: two checkpoint entries (3D rebuilt with WebGL; 3D tilt and zoom).
- `docs/mockups/`: v4, v5 (approved), v6 and v7 saved to the repo this session.
- Not in the repo and must NOT be committed: `.verify-screenshots/` (screenshots from testing), `desktop/dist` (gitignored), other untracked files that were already there (`.claude/*`, `.autoclaude/`, `Claude outputs/`, `.commitmsg.tmp`, `.heartbeats/` and similar).

## Verified

- Desktop tests: `npx vitest run` in `desktop/`: 4 files, 41 tests pass (run in the connected Linux VM, not on the Mac host).
- Build: `npx vite build --outDir /tmp/rigel-build-check --emptyOutDir` passes. Building into `desktop/dist` fails because deleting old files needs the user's delete permission.
- **In the real Tauri app** (screenshots in `.verify-screenshots/`):
  - 2D shows the flat ring map with all 14 servers (`step2`, `step9`).
  - 3D renders (`step4`). One upward drag moved the readout from "Tilt 27°" to "Tilt 39°" (`step6`). Scroll out gave "Zoom 0.5×" with the scene shrinking (`step7`). A sideways drag spins the rings (`step7`).
  - Clipping fixed: the bottom nodes (excalidraw, claude-code-usage) show in full at 39° (`step8`).
- **Not verified:** 2D spin (not built). Labels at other window sizes. Remembered 2D/3D choice after reload. The WebGL fallback to 2D in the real app.

## How to run and test (Mac)

- Sidecar (repo root): `./.venv/bin/python -m sidecar` (serves 127.0.0.1:5140).
- Desktop: `cd ~/Codehome/rigel/desktop && npm install && npm test && npm run dev` (dev server on localhost:1425, `strictPort: true`).
- Tauri app: `cd ~/Codehome/rigel/desktop/src-tauri && cargo run` (uses the running dev server; a second `npm run tauri dev` fails on the port). Process name is `app`, window title "Rigel".
- Mac shell from the Claude session: the `mcp__remote-devices__MacOS-MCP__Shell` tool. Screenshot: `screencapture -x <path>`, then stage with `device_stage_files` and `Read` it. Input helper: `/tmp/rigel_input.py` (Quartz mouse events; modes `tilt`, `spin`, `zoomin`, `zoomout`). It lives in `/tmp` on the Mac, so it may be gone.
- Mode buttons: `osascript` with `checkbox "2D"` or `checkbox "3D"` of `group "Map mode"` in `window "Rigel"`.
- Fresh Vite `strictPort` conflicts: if port 1425 is busy, reuse the running server instead of starting another.

## Known pitfalls (learned this session)

- `npm install` once fixed a missing `@rollup/rollup-linux-arm64-gnu` in `node_modules`. Lock file was fine.
- Dragging on 2D selects text (SVG) instead of rotating. Expected until 2D spin is built.
- Don't accept my screenshots of the Claude app as evidence of the Rigel window; check the window title.
- Edits in the mockup folder (`/mnt/user-data/outputs`) do not persist to the next session. The repo copies in `docs/mockups/` do.

## Next steps (in order)

1. Read `CLAUDE.md`, `docs/CONTINUATION.md`, this file, and `docs/mockups/toolbox-view-m2-v7-2d-flat.html`.
2. Ask Tony to approve v7 and to decide the overlap fix (see Decisions still open). Mock up the overlap fix before building it.
3. After approval: build 2D spin in `ToolBoxMap.jsx` (flat SVG, drag left/right rotates the server angles around the hub; no tilt or zoom); add tests for it; run `npx vitest run`.
4. Build the overlap fix (hint and readout bar below the scene; Servers panel beside the map). Verify in the Tauri app with the screenshot method above.
5. Check the 2D/3D toggle, the remembered choice after reload, and the WebGL fallback in the app.
6. Update `docs/CONTINUATION.md`. Remove `.verify-screenshots/` (Tony can delete it; it's untracked, so don't commit it).
7. Commit only when Tony asks, with the attribution lines. Push from the Mac.
