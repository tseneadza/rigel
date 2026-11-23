---
status: approved
phase: P1-M2
prd: docs/prd/rigel-view-screens.md
branch: feature/rigel-toolbox-view
base: ec50782
mockups: "Toolbox view M2: v3 (two rings by state), approved by Tony 2026-11-23 03:30. Earlier: v1, v2."
---

# M2: Toolbox view (read-only ToolBox map)

## Goal

Tony can open the Toolbox view and see ToolBox and its servers at a glance: which are running, which are cold (idle), and which have an error. 2D is the default; 3D is a toggle with a fallback.

## Decisions (Tony, 2026-11-23)

- ToolBox is the hub; Rigel and other agents sit at the edge as callers.
- Two rings by state: running, starting and stopping on the inner ring; cold and other states on the outer ring.
- `cold` is ToolBox's own idle label, shown in neutral grey. Red is reserved for an error.
- 2D | 3D toggle in the header; 2D opens first; the choice is remembered; 3D falls back to 2D with "3D unavailable here, showing 2D."
- Read-only. Current state only. No history.

## Acceptance criteria

- **AC-M2-1** Each ToolBox server appears once with its name, ToolBox state label, and tool count.
- **AC-M2-2** Running, starting and stopping servers are on the inner ring; every other state is on the outer ring.
- **AC-M2-3** A server with an error shows the error under its name. A server without one shows no error line.
- **AC-M2-4** The side panel gives the server count, running, cold, other counts, the tool total, and each error.
- **AC-M2-5** The 2D | 3D toggle switches the displayed mode, remembers the choice, and falls back to 2D with the reason when 3D can't render.
- **AC-M2-6** With no server data, the map says "No server detail yet."

## Verification

- `npm test` in `desktop/` (Vitest).
- `npx vite build` in `desktop/`.
- `./.venv/bin/python -m pytest -q sidecar/tests` in the repo root.
- Manual, on the Mac: ToolBox running, the Toolbox view shows 14 servers; stop one server and check it stays on the outer ring with its state.
