"""Registry of live ``AppHandler`` instances.

Handlers register themselves at import time (see the bottom of ``chrome.py``
/ ``vscode.py``); ``sidecar/handlers/__init__.py`` imports every handler
module so importing the ``handlers`` package is enough to populate this
registry. ``brain.py`` uses ``match()`` to route an utterance to a handler;
``executor.py`` and ``app.py`` use ``get()``/``all_handlers()`` to validate
and list them.
"""
from __future__ import annotations

from sidecar.handlers.base import AppHandler

_HANDLERS: dict[str, AppHandler] = {}


def register(handler: AppHandler) -> None:
    """Register ``handler`` under its ``app_id``. Re-registering the same
    ``app_id`` replaces the previous handler — useful for tests, harmless in
    production since each handler module registers exactly once on import."""
    _HANDLERS[handler.app_id] = handler


def get(app_id: str) -> AppHandler | None:
    return _HANDLERS.get(app_id)


def all_handlers() -> list[AppHandler]:
    return list(_HANDLERS.values())


def match(text: str) -> AppHandler | None:
    """Find the handler whose ``match_keywords`` best fits ``text``.

    Substring match against the lowercased text; the longest matching
    keyword wins (so "google chrome" beats "chrome" when both are present),
    breaking ties by registration order. Returns ``None`` if no handler's
    keywords appear in ``text`` at all — the caller (``brain.py``) then
    skips the per-app LLM call entirely rather than spending a request on
    text that clearly isn't about any known app.
    """
    lowered = text.lower()
    best: tuple[int, AppHandler] | None = None
    for handler in _HANDLERS.values():
        for keyword in handler.match_keywords:
            if keyword in lowered:
                if best is None or len(keyword) > best[0]:
                    best = (len(keyword), handler)
    return best[1] if best else None
