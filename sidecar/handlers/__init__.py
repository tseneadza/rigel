"""Per-app handlers — Rigel's "sub-agent" for each app it can operate on.

Importing this package registers every handler module below with
``registry.py``. Add a new app by writing a module here (subclass
``AppHandler`` from ``base.py``, register a singleton instance at the
bottom — see ``chrome.py``/``vscode.py``) and importing it here.
"""
from __future__ import annotations

from sidecar.handlers import chrome, vscode  # noqa: F401 - import registers each handler

__all__ = ["chrome", "vscode"]
