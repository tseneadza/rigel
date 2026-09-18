"""Rigel's brain — turns user text into a reply + a list of command intents.

``respond(text, llm_config)`` returns ``(reply, commands)`` where ``commands``
is a list of ``{action, args}`` dicts. Every provider, stub or LLM, only
detects intent — it never executes anything itself. Execution (behind an
explicit approval step) lives in ``executor.py``, wired up in ``app.py``.

When ``llm_config`` selects a real provider (Claude or Ollama, see
``llm_providers.py``), that provider produces both the reply and the
commands. If the provider call fails for any reason (no API key, model
unreachable, bad JSON back), this module falls back to the original regex
stub rather than leaving the user without a reply.
"""
from __future__ import annotations

import logging
import re

from sidecar import llm_providers

logger = logging.getLogger(__name__)

# Naive intent patterns — enough to prove the log-every-command path end to end.
# A real parser (LLM tool-calling) replaces this wholesale later.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("open_app",    re.compile(r"\bopen\s+(?P<target>.+)", re.I)),
    ("close_app",   re.compile(r"\b(?:close|quit|terminate)\s+(?P<target>.+)", re.I)),
    ("create_file", re.compile(r"\bcreate\s+(?:a\s+)?(?:new\s+)?file\s+(?:named\s+)?(?P<target>.+)", re.I)),
    ("delete_file", re.compile(r"\bdelete\s+(?P<target>.+)", re.I)),
]


def detect_commands(text: str) -> list[dict]:
    """Return command intents found in ``text`` as ``{action, args}`` dicts."""
    commands: list[dict] = []
    for action, pattern in _PATTERNS:
        m = pattern.search(text)
        if m:
            commands.append({"action": action, "args": {"target": m.group("target").strip(" .")}})
    return commands


def _stub_respond(text: str) -> tuple[str, list[dict]]:
    """The original regex-based stub. Pure + deterministic; also the fallback
    when a configured LLM provider is unavailable."""
    commands = detect_commands(text)

    if not text:
        return ("Standing by.", commands)

    if commands:
        actions = ", ".join(c["action"].replace("_", " ") for c in commands)
        reply = (
            f"Understood. I've logged that and I'm waiting on your approval to "
            f"{actions} — check the console. What's next?"
        )
    else:
        reply = f'Received: "{text}". Nothing to act on there — '\
                f"for now I'm logging our conversation. What is our next objective?"
    return (reply, commands)


def respond(text: str, llm_config: dict | None = None) -> tuple[str, list[dict]]:
    """Produce Rigel's reply and any command intents.

    ``llm_config`` is the ``{provider, claude_model, ollama_model,
    ollama_host}`` dict persisted via the sidecar's settings endpoints. With
    no provider configured (or on provider failure), falls back to the
    regex stub.
    """
    text = text.strip()
    provider = (llm_config or {}).get("provider", "stub")

    if not text:
        return ("Standing by.", [])

    if provider == "claude":
        try:
            return llm_providers.claude_respond(text, llm_config["claude_model"])
        except llm_providers.LLMError as e:
            logger.warning("Claude brain failed (%s); falling back to stub.", e)
    elif provider == "ollama":
        try:
            return llm_providers.ollama_respond(
                text,
                llm_config["ollama_model"],
                llm_config.get("ollama_host", llm_providers.DEFAULT_OLLAMA_HOST),
            )
        except llm_providers.LLMError as e:
            logger.warning("Ollama brain failed (%s); falling back to stub.", e)

    return _stub_respond(text)
