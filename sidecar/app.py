"""Rigel FastAPI sidecar.

Run standalone (dev):
    ./.venv/bin/python -m sidecar          # binds RIGEL_PORT or 5140

Endpoints (all under /api/rigel):
    POST /chat    — send a user message; logs the turn, previews + logs any
                    command intents ('blocked', or run immediately as 'ok'/
                    'error' when whitelisted, otherwise 'pending'), returns
                    Rigel's reply.
    POST /commands/{id}/approve — execute a pending command; updates its
                    status to 'ok' or 'error'.
    POST /commands/{id}/reject  — mark a pending command 'rejected'; never
                    executes it.
    GET  /state   — current orb state ('idle' | 'thinking' | 'speaking').
    GET  /logs    — recent conversation turns + command attempts.
    GET  /handlers — registered app handlers (sidecar/handlers/) and the
                    tools each exposes, for the whitelist UI.
    GET  /running-apps — every foreground app currently running, for the
                    orb window's open-apps list. macOS only; 503 elsewhere
                    or if Accessibility/System Events can't be reached.
    GET  /health  — liveness.
    GET  /settings/orb-config  — persisted orb sizes (expanded/minimized) and
                                  minimized-orb position (or defaults).
    POST /settings/orb-config  — save orb sizes/position.
    GET  /settings/llm-config  — persisted LLM brain provider/model (or defaults).
    POST /settings/llm-config  — save LLM brain provider/model.
    GET  /settings/llm-options — live-probed Claude/Ollama choices for the Settings UI.
    GET  /settings/voice-config — persisted voice/TTS preferences (or defaults).
    POST /settings/voice-config — save voice/TTS preferences.
    GET  /settings/whitelist-config — persisted per-action auto-approve rules
                                  (or defaults, all off).
    POST /settings/whitelist-config — save auto-approve rules. A whitelisted
                                  command runs immediately in /chat instead
                                  of coming back 'pending'.

Forked in spirit from AgenticOS's sidecar; intentionally self-contained
(SQLite, no MySQL, no AgenticOS imports).
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sidecar import brain, db, executor, llm_providers
from sidecar.handlers import menu_actions, registry

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
    diameter_px: int                           # expanded/resting ("maximum") size
    min_diameter_px: int = 90                  # minimized size
    position_corner: str                       # where the orb parks when minimized
    is_minimized: bool = False
    x_pct: float | None = None
    y_pct: float | None = None


class LLMConfig(BaseModel):
    provider: str = "stub"                    # 'stub' | 'claude' | 'ollama'
    claude_model: str | None = None
    ollama_model: str | None = None
    ollama_host: str = llm_providers.DEFAULT_OLLAMA_HOST


class VoiceConfig(BaseModel):
    tts_voice: str | None = None               # macOS voice name, e.g. "Samantha"
    speak_typed_replies: bool = False          # speak replies to typed (not just voice) turns
    enabled: bool = False                      # always-on wake-word listening


class ActionWhitelist(BaseModel):
    all: bool = False          # auto-approve every target for this action
    targets: list[str] = []    # auto-approve only these specific targets


class AppActionWhitelist(BaseModel):
    all: bool = False          # auto-approve every tool this app handler exposes
    tools: list[str] = []      # auto-approve only these specific tool names


class WhitelistConfig(BaseModel):
    open_app: ActionWhitelist = ActionWhitelist()
    close_app: ActionWhitelist = ActionWhitelist()
    create_file: ActionWhitelist = ActionWhitelist()
    delete_file: ActionWhitelist = ActionWhitelist()
    app_action: dict[str, AppActionWhitelist] = {}   # keyed by app_id


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

    llm_config = db.get_setting("llm_config")
    whitelist = db.get_setting("whitelist_config")
    reply, commands = brain.respond(body.text, llm_config)

    logged = []
    for cmd in commands:
        try:
            resolved_args = executor.preview(cmd["action"], cmd["args"])
        except executor.UnsafeCommandError as e:
            resolved_args, status, detail = cmd["args"], "blocked", str(e)
        else:
            if executor.is_whitelisted(cmd["action"], resolved_args, whitelist):
                status, detail = executor.execute(cmd["action"], resolved_args)
            else:
                status, detail = "pending", "Awaiting approval."

        cmd_id = db.log_command(
            action=cmd["action"],
            args=resolved_args,
            status=status,
            detail=detail,
            turn_id=user_turn_id,
        )
        logged.append({"id": cmd_id, "action": cmd["action"], "args": resolved_args, "status": status, "detail": detail})

    # brain.respond() writes its reply before knowing which commands turned
    # out unsafe — correct it here rather than teaching every brain
    # (stub + each LLM provider) about blocking.
    blocked = [c for c in logged if c["status"] == "blocked"]
    if blocked:
        reply += " " + " ".join(f"⚠ Blocked: {c['detail']}" for c in blocked)

    # Same reasoning as the 'blocked' correction above: a whitelisted
    # command already ran by the time brain.respond() wrote its "waiting on
    # your approval" line, so append the real outcome rather than leaving
    # that line to imply it's still pending.
    auto_run = [c for c in logged if c["status"] in ("ok", "error")]
    if auto_run:
        icons = {"ok": "✅", "error": "⚠"}
        reply += " " + " ".join(f"{icons[c['status']]} {c['detail']}" for c in auto_run)

    db.log_turn("rigel", reply)

    return {"reply": reply, "commands": logged}


def _pending_command_or_404(command_id: int) -> dict:
    cmd = db.get_command(command_id)
    if cmd is None:
        raise HTTPException(status_code=404, detail="command not found")
    if cmd["status"] != "pending":
        raise HTTPException(status_code=404, detail=f"command is '{cmd['status']}', not pending")
    return cmd


@app.post("/api/rigel/commands/{command_id}/approve")
def approve_command(command_id: int) -> dict:
    cmd = _pending_command_or_404(command_id)
    status, detail = executor.execute(cmd["action"], cmd["args"])
    db.update_command_status(command_id, status, detail)
    return {**cmd, "status": status, "detail": detail}


@app.post("/api/rigel/commands/{command_id}/reject")
def reject_command(command_id: int) -> dict:
    cmd = _pending_command_or_404(command_id)
    detail = "Rejected by user."
    db.update_command_status(command_id, "rejected", detail)
    return {**cmd, "status": "rejected", "detail": detail}


@app.get("/api/rigel/logs")
def logs(limit: int = 50) -> dict:
    return {
        "turns": db.recent_turns(limit),
        "commands": db.recent_commands(limit),
    }


def _validate_orb_config(config: OrbConfig) -> tuple[bool, str]:
    """Validate orb config values."""
    if not (200 <= config.diameter_px <= 620):
        return False, "diameter_px (expanded size) must be 200–620"
    if not (40 <= config.min_diameter_px <= 200):
        return False, "min_diameter_px (minimized size) must be 40–200"
    valid_corners = ("center", "top-left", "top-right", "bottom-left", "bottom-right", "custom")
    if config.position_corner not in valid_corners:
        return False, f"position_corner must be one of {valid_corners}"
    if config.position_corner == "custom":
        if config.x_pct is None or config.y_pct is None:
            return False, "x_pct and y_pct are required when position_corner is 'custom'"
        if not (0 <= config.x_pct <= 100) or not (0 <= config.y_pct <= 100):
            return False, "x_pct and y_pct must be between 0 and 100"
    return True, ""


_ORB_CONFIG_DEFAULTS = {
    "diameter_px": 620,
    "min_diameter_px": 90,
    "position_corner": "center",
    "is_minimized": False,
}


@app.get("/api/rigel/settings/orb-config")
def get_orb_config() -> dict:
    config = db.get_setting("orb_config")
    if config:
        # Backfill keys added after a config was first saved (e.g. an older
        # config predating min_diameter_px) so old settings don't break.
        return {**_ORB_CONFIG_DEFAULTS, **config}
    return dict(_ORB_CONFIG_DEFAULTS)


@app.post("/api/rigel/settings/orb-config")
def save_orb_config(body: OrbConfig) -> dict:
    valid, msg = _validate_orb_config(body)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    db.set_setting("orb_config", body.model_dump())
    return {"ok": True}


def _validate_llm_config(config: LLMConfig) -> tuple[bool, str]:
    """Validate LLM brain config values."""
    if config.provider not in ("stub", "claude", "ollama"):
        return False, "provider must be one of 'stub', 'claude', 'ollama'"
    if config.provider == "claude" and config.claude_model not in llm_providers.CLAUDE_MODELS:
        return False, f"claude_model must be one of {llm_providers.CLAUDE_MODELS}"
    if config.provider == "ollama":
        if not config.ollama_model:
            return False, "ollama_model is required when provider is 'ollama'"
        if not config.ollama_host:
            return False, "ollama_host is required when provider is 'ollama'"
    return True, ""


@app.get("/api/rigel/settings/llm-config")
def get_llm_config() -> dict:
    config = db.get_setting("llm_config")
    if config:
        return config
    return LLMConfig().model_dump()


@app.post("/api/rigel/settings/llm-config")
def save_llm_config(body: LLMConfig) -> dict:
    valid, msg = _validate_llm_config(body)
    if not valid:
        raise HTTPException(status_code=400, detail=msg)

    db.set_setting("llm_config", body.model_dump())
    return {"ok": True}


@app.get("/api/rigel/settings/llm-options")
def get_llm_options(ollama_host: str = llm_providers.DEFAULT_OLLAMA_HOST) -> dict:
    return {
        "claude": {
            "models": llm_providers.CLAUDE_MODELS,
            "api_key_configured": llm_providers.claude_api_key_configured(),
        },
        "ollama": llm_providers.probe_ollama(ollama_host),
    }


@app.get("/api/rigel/settings/voice-config")
def get_voice_config() -> dict:
    config = db.get_setting("voice_config")
    if config:
        return config
    return VoiceConfig().model_dump()


@app.post("/api/rigel/settings/voice-config")
def save_voice_config(body: VoiceConfig) -> dict:
    db.set_setting("voice_config", body.model_dump())
    return {"ok": True}


@app.get("/api/rigel/handlers")
def list_handlers() -> dict:
    """Registered app handlers and the tools each exposes, for the
    Settings UI's per-app whitelist section — it has no other way to know
    what handlers ``sidecar/handlers/`` currently registers."""
    return {
        "handlers": [
            {
                "app_id": h.app_id,
                "display_name": h.display_name,
                "tools": [{"name": t["name"], "description": t.get("description", "")} for t in h.tools],
            }
            for h in registry.all_handlers()
        ]
    }


@app.get("/api/rigel/running-apps")
def running_apps() -> dict:
    try:
        apps = menu_actions.list_running_apps()
    except menu_actions.MenuDiscoveryError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"apps": apps}


@app.get("/api/rigel/settings/whitelist-config")
def get_whitelist_config() -> dict:
    config = db.get_setting("whitelist_config")
    if config:
        return config
    return WhitelistConfig().model_dump()


@app.post("/api/rigel/settings/whitelist-config")
def save_whitelist_config(body: WhitelistConfig) -> dict:
    db.set_setting("whitelist_config", body.model_dump())
    return {"ok": True}


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=RIGEL_PORT, log_level="info")
