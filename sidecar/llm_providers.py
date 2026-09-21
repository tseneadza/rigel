"""Real LLM backends for Rigel's brain — the seam described in ``brain.py``.

Two providers, same contract as the regex stub: ``respond(text) -> (reply,
commands)`` where ``commands`` is a list of ``{action, args}`` dicts. Both
providers ask the model for that exact shape as JSON so downstream code
(logging, the "deferred" status, the UI) never has to know which brain
produced it.

Credentials: Claude reads ``ANTHROPIC_API_KEY`` (or any other credential
source the SDK resolves) from the environment — Rigel never stores or
displays an API key. Ollama is assumed local/trusted, no auth.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import urllib.error
import urllib.request
from typing import Any

import anthropic
import psutil

from sidecar.handlers.base import AppHandler

logger = logging.getLogger(__name__)


def _default_ollama_host() -> str:
    """Prefer explicit env config over the stock Ollama port, since a local
    install may be bound elsewhere (e.g. OLLAMA_HOST=0.0.0.0:12434)."""
    url = os.getenv("OLLAMA_API_URL")
    if url:
        return url.rstrip("/")
    host = os.getenv("OLLAMA_HOST")
    if host:
        bind_host, _, port = host.partition(":")
        if bind_host in ("", "0.0.0.0", "::"):
            bind_host = "localhost"  # a bind address isn't a connectable client target
        return f"http://{bind_host}:{port}" if port else f"http://{bind_host}"
    return "http://localhost:11434"


DEFAULT_OLLAMA_HOST = _default_ollama_host()

CLAUDE_MODELS = ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"]

SYSTEM_PROMPT = (
    "You are Rigel, a voice-activated desktop agent's conversational brain. "
    "Reply naturally and helpfully to the user's message. Separately, detect "
    "any command intents in their message and list them structurally, using "
    "exactly one of these four action names — never invent a different one: "
    "'open_app' (open/launch/start an app), 'close_app' (close/quit/"
    "terminate/exit/kill/shut down an app — all the same intent, regardless "
    "of which verb the user used), 'create_file', 'delete_file'. "
    "The executor that runs these matches the 'target' argument (an app "
    "name, or a file path) exactly, so give just the name/path itself — no "
    "articles ('the', 'a'), no trailing filler ('now', 'please', 'app'). "
    "You never execute anything yourself — you only detect and report intent; "
    "execution happens separately, behind the user's explicit approval. If "
    "you detect commands, your reply should say you understood and that "
    "you're waiting on approval, similar to: 'Understood. I've logged that "
    "and I'm waiting on your approval to <action> — check the console.' "
    "If there are no commands, just reply conversationally."
)


# Claude's strict structured-output validator requires every 'object' schema
# node to set additionalProperties: false explicitly — which rules out a
# genuinely free-form `args` dict (command args vary per action: a single
# "target", or several named fields). So args travels as a JSON-encoded
# string instead, and _parse_response_json() decodes it back into a dict.
# Both providers use the same wire shape for consistency.
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "commands": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["open_app", "close_app", "create_file", "delete_file"],
                    },
                    "args_json": {
                        "type": "string",
                        "description": "JSON-encoded object of this action's arguments, e.g. '{\"target\": \"Chrome\"}'.",
                    },
                },
                "required": ["action", "args_json"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["reply", "commands"],
    "additionalProperties": False,
}


class LLMError(Exception):
    """Raised when a provider can't produce a (reply, commands) pair."""


def _normalize_command(cmd: dict) -> dict:
    """Decode the wire shape ({action, args_json}) into the ({action, args})
    shape the rest of the codebase (db.log_command, the UI) expects. Also
    tolerates a plain `args` object, since Ollama's JSON mode isn't schema-
    enforced and may not follow the args_json convention exactly."""
    action = str(cmd.get("action", ""))
    if "args_json" in cmd:
        raw_args = cmd.get("args_json") or "{}"
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except json.JSONDecodeError:
            args = {}
    else:
        args = cmd.get("args")
    if not isinstance(args, dict):
        args = {}
    return {"action": action, "args": args}


def _parse_response_json(raw: str) -> tuple[str, list[dict]]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise LLMError(f"model returned invalid JSON: {e}") from e
    if not isinstance(data, dict) or "reply" not in data:
        raise LLMError("model JSON missing 'reply'")
    commands = data.get("commands") or []
    if not isinstance(commands, list):
        raise LLMError("model JSON 'commands' is not a list")
    commands = [_normalize_command(c) for c in commands if isinstance(c, dict)]
    return str(data["reply"]), commands


# ── Claude ───────────────────────────────────────────────────────────────

def claude_respond(text: str, model: str) -> tuple[str, list[dict]]:
    if model not in CLAUDE_MODELS:
        raise LLMError(f"unknown Claude model: {model!r}")

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
            output_config={"format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}},
        )
    except anthropic.AuthenticationError as e:
        raise LLMError(f"Claude authentication failed: {e}") from e
    except anthropic.RateLimitError as e:
        raise LLMError(f"Claude rate limited: {e}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError(f"Claude connection error: {e}") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Claude API error ({e.status_code}): {e.message}") from e
    except TypeError as e:
        # Raised by the SDK's own credential resolution, not an API call —
        # e.g. no ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN / auth profile set.
        raise LLMError(f"Claude credentials not configured: {e}") from e

    raw = next((b.text for b in response.content if b.type == "text"), "")
    return _parse_response_json(raw)


def claude_app_action(text: str, model: str, handler: AppHandler) -> list[dict]:
    """Ask ``handler``'s own scoped Claude call to turn ``text`` into zero or
    one ``app_action`` command intents.

    Unlike ``claude_respond``, this doesn't produce a reply — ``brain.py``
    already has one from the shared four-verb pass. This call exists purely
    to let a handler's own tool vocabulary (which ``respond``'s fixed
    ``RESPONSE_SCHEMA`` knows nothing about) decide whether the utterance
    maps to one of *its* actions, using real Claude tool-use rather than the
    JSON-schema trick ``RESPONSE_SCHEMA`` relies on — each handler's
    ``tools`` list varies, so a single shared schema can't describe it.
    """
    if model not in CLAUDE_MODELS:
        raise LLMError(f"unknown Claude model: {model!r}")

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=512,
            system=handler.system_prompt,
            tools=handler.tools,
            tool_choice={"type": "auto"},
            messages=[{"role": "user", "content": text}],
        )
    except anthropic.AuthenticationError as e:
        raise LLMError(f"Claude authentication failed: {e}") from e
    except anthropic.RateLimitError as e:
        raise LLMError(f"Claude rate limited: {e}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError(f"Claude connection error: {e}") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Claude API error ({e.status_code}): {e.message}") from e
    except TypeError as e:
        raise LLMError(f"Claude credentials not configured: {e}") from e

    commands = []
    for block in response.content:
        if block.type == "tool_use":
            commands.append({
                "action": "app_action",
                "args": {"app_id": handler.app_id, "tool": block.name, "tool_args": block.input},
            })
    return commands


# ── Ollama ───────────────────────────────────────────────────────────────

def _ollama_request(host: str, path: str, body: dict | None, timeout: float) -> dict[str, Any]:
    url = host.rstrip("/") + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url, data=data, method="POST" if data is not None else "GET",
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ollama_respond(text: str, model: str, host: str = DEFAULT_OLLAMA_HOST) -> tuple[str, list[dict]]:
    schema_hint = (
        "Respond with ONLY a JSON object of the exact shape "
        '{"reply": "<string>", "commands": [{"action": '
        "<one of 'open_app'|'close_app'|'create_file'|'delete_file', exactly, never another string>, "
        '"args_json": "<JSON-encoded string of an object, e.g. \'{\\"target\\": \\"Chrome\\"}\'>"}]} '
        "— no prose outside the JSON. args_json must be a STRING containing encoded JSON, not a nested object."
    )
    body = {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT + " " + schema_hint},
            {"role": "user", "content": text},
        ],
    }
    keep_alive = os.getenv("OLLAMA_KEEP_ALIVE")
    if keep_alive:
        # Explicit per-request keep_alive so Rigel's responsiveness intent
        # doesn't silently depend on how the Ollama server happened to be
        # launched — it holds the model resident between chat turns.
        body["keep_alive"] = keep_alive
    try:
        result = _ollama_request(host, "/api/chat", body, timeout=30.0)
    except urllib.error.URLError as e:
        raise LLMError(f"Ollama unreachable at {host}: {e}") from e
    except TimeoutError as e:
        raise LLMError(f"Ollama timed out at {host}: {e}") from e

    raw = (result.get("message") or {}).get("content", "")
    return _parse_response_json(raw)


# ── System / hardware probing ───────────────────────────────────────────

def system_ram_gb() -> float:
    return round(psutil.virtual_memory().total / (1024 ** 3), 1)


def claude_api_key_configured() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def _fit_label(model_gb: float, ram_gb: float) -> str:
    if ram_gb <= 0:
        return "unknown"
    ratio = model_gb / ram_gb
    if ratio < 0.5:
        return "comfortable"
    if ratio < 0.8:
        return "borderline"
    return "too_large"


def _ollama_binary_present() -> bool:
    path = os.getenv("OLLAMA")
    if path and os.path.isfile(path):
        return True
    return shutil.which("ollama") is not None


def probe_ollama(host: str = DEFAULT_OLLAMA_HOST) -> dict:
    """Live-probe a local/remote Ollama for installed models and size-fit
    against this machine's actual RAM. Never raises — callers always get a
    usable dict, even when Ollama isn't running.
    """
    ram_gb = system_ram_gb()
    try:
        result = _ollama_request(host, "/api/tags", None, timeout=1.5)
    except Exception as e:  # noqa: BLE001 - any probe failure just means "not available"
        logger.info("Ollama not reachable at %s: %s", host, e)
        return {
            "installed": False,
            "binary_present": _ollama_binary_present(),
            "host": host,
            "models": [],
            "system_ram_gb": ram_gb,
        }

    models = []
    for m in result.get("models", []):
        name = m.get("name") or m.get("model")
        size_bytes = m.get("size", 0)
        if not name:
            continue
        size_gb = round(size_bytes / (1024 ** 3), 1)
        models.append({"name": name, "size_gb": size_gb, "fit": _fit_label(size_gb, ram_gb)})

    return {
        "installed": True,
        "binary_present": True,
        "host": host,
        "models": models,
        "system_ram_gb": ram_gb,
    }
