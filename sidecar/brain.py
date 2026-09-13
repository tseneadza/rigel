"""Rigel's brain — turns user text into a reply + a list of command intents.

FIRST-SLICE STUB. This is deliberately a stub with a clean seam so a real LLM
(Claude) can drop in later without touching the sidecar or the UI:

  * ``respond(text)`` returns ``(reply, commands)`` where ``commands`` is a list
    of ``{action, args}`` dicts Rigel *would* execute.
  * Command execution is deferred (project scope), so callers log each command
    with status ``"deferred"`` — but the intent is still detected and recorded
    from day one, satisfying "log the commands Rigel tries to implement."

To swap in Claude later: replace the body of ``respond`` with an API call that
returns the same ``(reply, commands)`` shape. Nothing downstream changes.
"""
from __future__ import annotations

import re

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


def respond(text: str) -> tuple[str, list[dict]]:
    """Produce Rigel's reply and any command intents. Pure + deterministic."""
    text = text.strip()
    commands = detect_commands(text)

    if not text:
        return ("Standing by.", commands)

    if commands:
        actions = ", ".join(c["action"].replace("_", " ") for c in commands)
        reply = (
            f"Understood. I would {actions} — but command execution is not wired "
            f"up yet, so I've logged the intent instead. What's next?"
        )
    else:
        reply = f'Received: "{text}". My execution layer is still coming online — '\
                f"for now I'm logging our conversation. What is our next objective?"
    return (reply, commands)
