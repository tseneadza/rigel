"""Rigel FastAPI sidecar.

Run standalone (dev):
    ./.venv/bin/python -m sidecar          # binds RIGEL_PORT or 5140

Endpoints (all under /api/rigel):
    POST /chat    — send a user message; logs the turn, logs any command
                    intents (as 'deferred'), returns Rigel's reply.
    GET  /state   — current orb state ('idle' | 'thinking' | 'speaking').
    GET  /logs    — recent conversation turns + command attempts.
    GET  /health  — liveness.
    GET  /settings/orb-config  — persisted orb size/position (or defaults).
    POST /settings/orb-config  — save orb size/position.

Forked in spirit from AgenticOS's sidecar; intentionally self-contained
(SQLite, no MySQL, no AgenticOS imports).
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sidecar import brain, db

RIGEL_PORT = int(os.getenv("RIGEL_PORT", "5140"))

app = FastAPI(title="Rigel Sidecar", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "tauri://localhost",
        "http://tauri.localhost",
        "http://localhost:1425",   # Rigel Vite dev server
        "http://localhost:1420",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatIn(BaseModel):
    text: str


class OrbConfig(BaseModel):
    diameter_px: int
    position_corner: str
    is_minimized: bool = False


@app.get("/api/rigel/health")
def health() -> dict:
    return {"ok": True, "service": "rigel-sidecar", "version": "0.1.0"}


@app.get("/api/rigel/state")
def state() -> dict:
    # First slice: static idle. Voice/thinking states arrive with the LLM slice.
    return {"state": "idle", "caption": "Standing by."}


@app.post("/api/rigel/chat")
def chat(body: ChatIn) -> dict:
    user_turn_id = db.log_turn("user", body.text)

    reply, commands = brain.respond(body.text)

    logged = []
    for cmd in commands:
        cmd_id = db.log_command(
            action=cmd["action"],
            args=cmd["args"],
            status="deferred",                     # execution not wired up yet
            detail="Intent detected; execution layer not implemented.",
            turn_id=user_turn_id,
        )
        logged.append({"id": cmd_id, **cmd, "status": "deferred"})

    db.log_turn("rigel", reply)

    return {"reply": reply, "commands": logged}


@app.get("/api/rigel/logs")
def logs(limit: int = 50) -> dict:
    return {
        "turns": db.recent_turns(limit),
        "commands": db.recent_commands(limit),
    }


def _validate_orb_config(config: OrbConfig) -> tuple[bool, str]:
    """Validate orb config values."""
    if not (60 <= config.diameter_px <= 620):
        return False, "diameter_px must be 60–620"
    valid_corners = ("center", "top-left", "top-right", "bottom-left", "bottom-right")
    if config.position_corner not in valid_corners:
        return False, f"position_corner must be one of {valid_corners}"
    return True, ""


@app.get("/api/rigel/settings/orb-config")
def get_orb_config() -> dict:
    config = db.get_setting("orb_config")
    if config:
        return config
    return {
        "diameter_px": 620,
        "position_corner": "center",
        "is_minimized": False,
    }


@app.post("/api/rigel/settings/orb-config")
def save_orb_config(body: OrbConfig) -> dict:
    valid, msg = _validate_orb_config(body)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    db.set_setting("orb_config", body.model_dump())
    return {"ok": True}


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=RIGEL_PORT, log_level="info")
