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
    GET  /settings/toolbox-config — ToolBox tool use: enabled, url override,
                                  max_steps (or defaults).
    POST /settings/toolbox-config — save it.
    GET  /toolbox/status          — is ToolBox reachable; servers/tool counts;
                                  whether the selected brain can use tools.
    GET  /toolbox/approvals       — approvals a ToolBox server is waiting on
                                  (MCP elicitation), for the console card.
                                  Polled while a /chat is in flight.
    POST /toolbox/approvals/{id}/answer    — {decision: approve|decline, via}.
    POST /toolbox/approvals/{id}/interpret — {text, via}: classify a spoken or
                                  typed answer; applies it when clear, else
                                  returns a follow_up question to ask.

Forked in spirit from AgenticOS's sidecar; intentionally self-contained
(SQLite, no MySQL, no AgenticOS imports).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sidecar import approvals, brain, db, executor, llm_providers, toolbox_client
from sidecar.handlers import menu_actions, registry

RIGEL_PORT = int(os.getenv("RIGEL_PORT", "5140"))

app = FastAPI(title="Rigel Sidecar", version="0.1.0")


def _setup_approval_audit_log() -> None:
    """Approval decisions go to their own file, so every approve, decline or
    expiry can be traced to how it was given (click, voice or typed)."""
    log_dir = Path.home() / "Library" / "Logs" / "com.tonyseneadza.rigel"
    log_dir.mkdir(parents=True, exist_ok=True)
    audit = logging.getLogger("rigel.approvals")
    if not any(isinstance(h, logging.FileHandler) for h in audit.handlers):
        handler = logging.FileHandler(log_dir / "approvals.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        audit.addHandler(handler)
    audit.setLevel(logging.INFO)


_setup_approval_audit_log()

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


class MenuActionWhitelist(BaseModel):
    all: bool = False                  # auto-approve every menu click for this app
    menu_paths: list[list[str]] = []   # auto-approve only these specific menu paths
    # Note: executor.is_whitelisted() still forces approval for a
    # dangerous-sounding item (menu_actions.is_dangerous()) regardless of
    # either field here — see executor.py's is_whitelisted docstring.


class ToolBoxConfig(BaseModel):
    enabled: bool = True          # let the brain find and run ToolBox tools
    url: str | None = None        # None = auto (~/.toolbox/service.json)
    max_steps: int = 5            # need+call steps per reply (runaway guard)


class ApprovalAnswer(BaseModel):
    decision: str                 # 'approve' | 'decline'
    via: str = "click"            # 'click' | 'voice' | 'typed'


class ApprovalUtterance(BaseModel):
    text: str
    via: str = "voice"


class WhitelistConfig(BaseModel):
    open_app: ActionWhitelist = ActionWhitelist()
    close_app: ActionWhitelist = ActionWhitelist()
    create_file: ActionWhitelist = ActionWhitelist()
    delete_file: ActionWhitelist = ActionWhitelist()
    app_action: dict[str, AppActionWhitelist] = {}       # keyed by app_id
    click_menu_item: dict[str, MenuActionWhitelist] = {}  # keyed by app process name


class MicWakeWordConfig(BaseModel):
    enabled: bool = True          # wake-word listening on; off = muted (FR-18)


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
    history = db.conversation_history(db.active_conversation_id(), user_turn_id)

    llm_config = db.get_setting("llm_config")
    whitelist = db.get_setting("whitelist_config")
    toolbox_config = {**ToolBoxConfig().model_dump(), **(db.get_setting("toolbox_config") or {})}
    result = brain.respond_with_tools(body.text, llm_config, toolbox_config, history=history)
    reply, commands = result["reply"], result["commands"]

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

    reply_turn_id = db.log_turn("rigel", reply)
    db.log_tool_steps(reply_turn_id, result["tool_steps"])

    return {
        "reply": reply,
        "commands": logged,
        "tool_steps": result["tool_steps"],
        "toolbox": result["toolbox"],
    }


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
    turns = db.recent_turns(limit)
    steps = db.tool_steps_for_turns([t["id"] for t in turns if t["role"] == "rigel"])
    for t in turns:
        if t["id"] in steps:
            t["tool_steps"] = steps[t["id"]]
    return {
        "turns": turns,
        "commands": db.recent_commands(limit),
    }


def _toolbox_config() -> dict:
    return {**ToolBoxConfig().model_dump(), **(db.get_setting("toolbox_config") or {})}


@app.get("/api/rigel/settings/toolbox-config")
def get_toolbox_config() -> dict:
    return _toolbox_config()


@app.post("/api/rigel/settings/toolbox-config")
def save_toolbox_config(body: ToolBoxConfig) -> dict:
    if not (1 <= body.max_steps <= 15):
        raise HTTPException(status_code=400, detail="max_steps must be 1–15")
    if body.url is not None and body.url.strip() and not body.url.startswith(("http://127.0.0.1", "http://localhost", "http://toolbox")):
        raise HTTPException(status_code=400, detail="url must be a local ToolBox address")
    cfg = body.model_dump()
    cfg["url"] = (cfg["url"] or "").strip() or None
    db.set_setting("toolbox_config", cfg)
    return {"ok": True}


@app.get("/api/rigel/toolbox/status")
def toolbox_status() -> dict:
    from sidecar import tool_brain

    st = toolbox_client.status(_toolbox_config())
    llm = db.get_setting("llm_config") or {}
    provider = llm.get("provider", "stub")
    if provider == "claude":
        st["brain"] = {"provider": "claude", "tools": True}
    elif provider == "ollama":
        model = llm.get("ollama_model")
        st["brain"] = {
            "provider": "ollama", "model": model,
            "tools": bool(model) and tool_brain.ollama_supports_tools(
                model, llm.get("ollama_host", llm_providers.DEFAULT_OLLAMA_HOST)),
        }
    else:
        st["brain"] = {"provider": provider, "tools": False}
    return st


@app.get("/api/rigel/toolbox/approvals")
def toolbox_approvals() -> dict:
    return {"approvals": approvals.pending()}


def _approval_or_404(approval_id: str) -> approvals.Approval:
    a = approvals.get(approval_id)
    if a is None:
        raise HTTPException(status_code=404, detail="approval not found")
    return a


@app.post("/api/rigel/toolbox/approvals/{approval_id}/answer")
def answer_approval(approval_id: str, body: ApprovalAnswer) -> dict:
    if body.decision not in ("approve", "decline"):
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'decline'")
    if body.via not in ("click", "voice", "typed"):
        raise HTTPException(status_code=400, detail="via must be click, voice or typed")
    a = _approval_or_404(approval_id)
    if not a.resolve(body.decision, body.via):
        raise HTTPException(status_code=409, detail=f"approval is '{a.status}', not pending")
    return a.public()


@app.post("/api/rigel/toolbox/approvals/{approval_id}/interpret")
def interpret_approval(approval_id: str, body: ApprovalUtterance) -> dict:
    a = _approval_or_404(approval_id)
    if a.status != "pending":
        return {"decision": "closed", "status": a.status, "approval": a.public()}
    via = body.via if body.via in ("voice", "typed") else "voice"
    return approvals.interpret(a, body.text, db.get_setting("llm_config"), via=via)


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


_MIC_WAKE_WORD_KEY = "mic_wake_word_enabled"


@app.get("/api/rigel/settings/mic-wake-word")
def get_mic_wake_word() -> dict:
    """Mute state (NFR-2). Default on when nothing has been saved yet."""
    config = db.get_setting(_MIC_WAKE_WORD_KEY)
    return {"enabled": bool(config["enabled"]) if config else True}


@app.post("/api/rigel/settings/mic-wake-word")
def save_mic_wake_word(body: MicWakeWordConfig) -> dict:
    db.set_setting(_MIC_WAKE_WORD_KEY, {"enabled": body.enabled})
    return {"ok": True, "enabled": body.enabled}


@app.get("/api/rigel/conversations")
def list_conversations() -> dict:
    """History list (FR-16). Newest first; the active one is marked."""
    return {"active_id": db.active_conversation_id(),
            "conversations": db.list_conversations()}


@app.post("/api/rigel/conversations/new")
def new_conversation() -> dict:
    """New Chat (FR-15/FR-17). Older transcripts stay in history; nothing is deleted."""
    return {"ok": True, "id": db.start_new_conversation()}


@app.get("/api/rigel/conversations/{conversation_id}/turns")
def conversation_turns(conversation_id: int) -> dict:
    return {"turns": db.conversation_turns(conversation_id)}


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
            "api_key_source": llm_providers.claude_api_key_source(),
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
