"""``AppHandler`` — the per-app "sub-agent" contract.

Rigel's original executor (``executor.py``) speaks a fixed, four-verb
vocabulary (open/close an app, create/delete a file) resolved by one shared
LLM call in ``brain.py``. That's enough to launch or quit an app, but not to
operate *inside* one ("new tab in Chrome", "open this folder in VS Code").

An ``AppHandler`` is a small, self-contained description of one app's own
vocabulary: a system prompt giving an LLM that app's persona, and a Claude
tool-use ``tools`` schema listing exactly the actions this app supports.
``brain.py`` routes a matched utterance to the handler's own scoped LLM call
(``llm_providers.claude_app_action``) instead of forcing it through the
shared four-verb schema; the resulting tool call becomes a single
``app_action`` command, previewed/whitelisted/executed by ``executor.py``
exactly like any other command. A handler never calls an LLM or touches the
approval flow itself — same separation of concerns as the rest of the
codebase: detect intent here, execute only in ``executor.py``.

Concrete handlers (``chrome.py``, ``vscode.py``, ...) subclass this, define
their own ``tools``, and implement ``execute_tool`` using whatever OS hooks
that app supports (AppleScript, a CLI, ...). They register themselves with
``registry.py`` at import time.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class AppHandler(ABC):
    """One app's intent vocabulary + the code that carries it out.

    Subclasses set the four class-level attributes below and implement
    ``execute_tool``. Instances are stateless and safe to share as module-
    level singletons (see ``chrome.py``/``vscode.py`` for the pattern).
    """

    #: Stable identifier used in whitelist config, logs, and the registry —
    #: never shown to the user directly. Lowercase, no spaces (e.g. "chrome").
    app_id: str

    #: Human-readable name for approval cards and Settings UI (e.g. "Google Chrome").
    display_name: str

    #: Lowercase words/phrases that make ``registry.match()`` route an
    #: utterance to this handler. Matching is substring-based against the
    #: lowercased text — keep these specific enough to avoid false positives
    #: (e.g. "chrome", "google chrome", not "browser").
    match_keywords: list[str]

    #: System prompt for this handler's scoped Claude call. Should describe
    #: the app briefly and instruct the model to call exactly one of
    #: ``tools`` (or none, if the request doesn't actually match an action).
    system_prompt: str

    #: Claude tool-use schema (the ``tools`` param of ``messages.create``) —
    #: one entry per action this handler supports. ``executor.preview()``
    #: validates a requested tool name against this list before anything
    #: is logged or run.
    tools: list[dict]

    @abstractmethod
    def execute_tool(self, tool_name: str, tool_input: dict) -> tuple[str, str]:
        """Run ``tool_name`` (one of ``self.tools``) with ``tool_input``.

        Returns ``(status, detail)`` with ``status`` one of ``'ok' | 'error'``
        — same contract as ``executor._execute_macos``. Must never raise;
        ``executor.execute()`` wraps callers in a last-resort guard, but a
        handler should catch its own expected failure modes (app not
        running, AppleScript error, ...) and report them as ``'error'``
        rather than relying on that guard.
        """
        raise NotImplementedError
