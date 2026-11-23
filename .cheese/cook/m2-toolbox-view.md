status: ok
next: age
artifact: .cheese/specs/m2-toolbox-view.md
taste_test: deferred-to-orchestrator
durable_flags: none
baseline: none
Toolbox view M2: two-ring server map (running inner, cold/other outer), side summary, hover titles, ring and summary tests; sidecar adapter already passing.

## Package report
- Files: desktop/src/components/ToolBoxMap.jsx (rewritten to v3 layout); desktop/src/__tests__/ToolBoxMap.test.jsx (+ring and summary tests); desktop/src/styles.css (ring and side-panel rules); .cheese/specs/m2-toolbox-view.md (spec, approved).
- Earlier, in this branch: toolboxView.js, ToolBoxModeToggle.jsx, ViewArea.jsx, App.jsx, sidecar server_rows adapter and tests.
- Checks: NOT RUN in this session (Linux sandbox; the node_modules are macOS-only). Required on the Mac: npm test, npx vite build, sidecar pytest.
- Cook's Press loop and the cook.pyz scripts were not run: they need the Mac's Claude Code environment. Behavior work normally goes through Press; this was done inline.
- Risks: the layout is unverified in a browser; 14 labels may still crowd on the outer ring at narrow widths.
