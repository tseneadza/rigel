"""Rigel sidecar — lean FastAPI service backing the Rigel orb.

Standalone by design: Rigel keeps its own SQLite log/memory store
(`~/.rigel/rigel.db`) and shares nothing with the AgenticOS sidecar.
Forked in spirit from AgenticOS's `gui/sidecar`, not imported from it.
"""
