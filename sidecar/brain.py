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

On top of that shared four-verb pass (open/close app, create/delete file),
``respond()`` separately checks whether ``text`` matches a registered
``AppHandler`` (see ``sidecar/handlers/``) — an app's own richer vocabulary
("new tab in Chrome") that the shared schema can't express. A match adds
one or more ``app_action`` commands via that handler's own scoped Claude
call (``_app_commands``); it never replaces or blocks the shared pass's
reply and commands, only adds to them.

Before any of that, ``respond()`` also checks for a "what apps are open"
style query and answers it directly (``_running_apps_reply``) — a pure
read, so it skips the provider entirely (no LLM call needed for a fully
deterministic answer) and never produces a command, so it's never
approval-gated.
"""
from __future__ import annotations

import logging
import re

from sidecar import llm_providers
from sidecar.handlers import menu_actions, registry

logger = logging.getLogger(__name__)

# Naive intent patterns — enough to prove the log-every-command path end to end.
# A real parser (LLM tool-calling) replaces this wholesale later.
# close_app recognizes "close", "quit", "terminate" and the synonyms people
# actually say ("kill Chrome", "shut down Slack", "exit Preview").
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("open_app",    re.compile(r"\bopen\s+(?P<target>.+)", re.I)),
    ("close_app",   re.compile(r"\b(?:close|quit|terminate|exit|kill|shut down)\s+(?P<target>.+)", re.I)),
    ("create_file", re.compile(r"\bcreate\s+(?:a\s+)?(?:new\s+)?file\s+(?:named\s+)?(?P<target>.+)", re.I)),
    ("delete_file", re.compile(r"\bdelete\s+(?P<target>.+)", re.I)),
]

# The patterns above capture everything after the verb, so natural phrasing
# ("close the Chrome app", "quit Chrome now", "terminate Slack please") drags
# filler words into the target and breaks the exact-name match `executor.py`
# needs (`open -a "the Chrome app"` won't resolve). Strip it off the capture.
_LEADING_FILLER = re.compile(r"^(?:the|a|an|my|out of)\s+", re.I)
_TRAILING_FILLER = re.compile(r"(?:\s+(?:app|application|now|please|for me))+$", re.I)

# Matches "what apps are open", "which applications are running", "what's
# open", etc. Deliberately narrow (an app/application noun, or the "what's
# open" short form) so it doesn't fire on unrelated uses of "open"/"running"
# elsewhere in a sentence — this bypasses the LLM entirely, so a false match
# would silently swallow a real request instead of just answering it wrong.
_RUNNING_APPS_QUERY = re.compile(
    r"\b(?:what|which)(?:'s|\s+is|\s+are)?\s+(?:apps?|applications?)\s+(?:are\s+|is\s+)?(?:open|running)\b"
    r"|\bwhat'?s\s+(?:open|running)\b",
    re.I,
)


def _clean_target(raw: str) -> str:
    target = raw.strip(" .!?\"'")
    target = _TRAILING_FILLER.sub("", target)
    target = _LEADING_FILLER.sub("", target)
    return target.strip(" .!?\"'")


def detect_commands(text: str) -> list[dict]:
    """Return command intents found in ``text`` as ``{action, args}`` dicts."""
    commands: list[dict] = []
    for action, pattern in _PATTERNS:
        m = pattern.search(text)
        if m:
            commands.append({"action": action, "args": {"target": _clean_target(m.group("target"))}})
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

    if not text:
        return ("Standing by.", [])

    running_apps_reply = _running_apps_reply(text)
    if running_apps_reply is not None:
        return (running_apps_reply, [])

    provider = (llm_config or {}).get("provider", "stub")

    if provider == "claude":
        try:
            reply, commands = llm_providers.claude_respond(text, llm_config["claude_model"])
        except llm_providers.LLMError as e:
            logger.warning("Claude brain failed (%s); falling back to stub.", e)
        else:
            return reply, commands + _app_commands(text, llm_config)
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


def _running_apps_reply(text: str) -> str | None:
    """Direct answer to a "what apps are open" style query, or ``None`` if
    ``text`` isn't one. A pure read — never produces a command, so it's
    never approval-gated, and it's checked before any provider call since
    the answer is fully deterministic (no LLM needed to look up a fact)."""
    if not _RUNNING_APPS_QUERY.search(text):
        return None
    try:
        apps = menu_actions.list_running_apps()
    except menu_actions.MenuDiscoveryError as e:
        return f"I couldn't check what's open: {e}"
    if not apps:
        return "I couldn't find any open apps."
    return "Open apps: " + ", ".join(apps) + "."


def _app_commands(text: str, llm_config: dict) -> list[dict]:
    """Route ``text`` to a matching per-app handler's own scoped Claude
    call, if one matches. Handler support is Claude-only for now — Ollama's
    JSON-mode prompting (see ``ollama_respond``) doesn't have an equivalent
    to real tool-use, so extending this to Ollama needs its own design
    rather than reusing ``claude_app_action`` as-is. Failure here (no match,
    or the scoped call itself failing) never blocks the reply already
    produced by the shared four-verb pass — it only ever adds commands, and
    an empty list is a perfectly normal outcome, not a fallback condition.
    """
    handler = registry.match(text)
    if handler is None:
        return []
    try:
        return llm_providers.claude_app_action(text, llm_config["claude_model"], handler)
    except llm_providers.LLMError as e:
        logger.warning("App handler '%s' call failed (%s); skipping.", handler.app_id, e)
        return []
