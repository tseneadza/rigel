"""Rigel's execution layer — runs an approved command intent for real.

Two-step contract, matched by ``app.py``:

  ``preview(action, args)``   — resolve + validate args *before* the command
                                 is even logged, so what the user is asked to
                                 approve is exactly what will run. Raises
                                 ``UnsafeCommandError`` for anything that
                                 fails validation; callers should log that as
                                 ``blocked`` and skip the approval step
                                 entirely — there's nothing safe to approve.

  ``execute(action, args)``   — actually run a *previewed* action. Never
                                 raises: every failure mode is caught and
                                 returned as ``("error", detail)`` so callers
                                 don't have to guess what might go wrong.

macOS only for now — other platforms raise ``NotImplementedError``, which
``execute`` turns into an ordinary ``"error"`` status rather than a crash.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Sandbox root for relative create/delete targets, and the only tree an
# absolute target is allowed to resolve inside.
_HOME = Path.home().resolve()
_SANDBOX_DIR = _HOME / "rigel-files"


class UnsafeCommandError(Exception):
    """Raised by ``preview`` when a command's args fail validation."""


def _resolve_file_target(target: str) -> Path:
    raw = Path(target).expanduser()
    if raw.is_absolute():
        path = raw
    else:
        # This is Rigel's own directory, not a user-specified path — safe
        # to create, unlike the "never auto-create dirs" rule for
        # create_file's parent below.
        _SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
        path = _SANDBOX_DIR / raw
    resolved = path.resolve()
    try:
        resolved.relative_to(_HOME)
    except ValueError:
        raise UnsafeCommandError(f"'{target}' resolves outside the home directory — refused.")
    return resolved


def preview(action: str, args: dict) -> dict:
    """Resolve ``args`` into exactly what ``execute`` will use, validating
    as it goes. Returns a new args dict; raises ``UnsafeCommandError`` on
    anything unsafe."""
    if action in ("open_app", "close_app"):
        target = str(args.get("target", "")).strip()
        if not target:
            raise UnsafeCommandError("no app name given.")
        return {"target": target}

    if action in ("create_file", "delete_file"):
        target = str(args.get("target", "")).strip()
        if not target:
            raise UnsafeCommandError("no file path given.")
        resolved = _resolve_file_target(target)
        if action == "delete_file":
            if not resolved.exists():
                raise UnsafeCommandError(f"'{resolved}' does not exist.")
            if resolved.is_dir():
                raise UnsafeCommandError(f"'{resolved}' is a directory — refused.")
        return {"path": str(resolved)}

    raise UnsafeCommandError(f"unknown action '{action}'.")


def _execute_macos(action: str, args: dict) -> tuple[str, str]:
    if action == "open_app":
        target = args["target"]
        result = subprocess.run(["open", "-a", target], capture_output=True, text=True)
        if result.returncode != 0:
            return ("error", result.stderr.strip() or f"failed to open '{target}'.")
        return ("ok", f"Opened {target}.")

    if action == "close_app":
        target = args["target"]
        script = f'quit app "{target}"'
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        if result.returncode != 0:
            return ("error", result.stderr.strip() or f"failed to close '{target}'.")
        return ("ok", f"Closed {target}.")

    if action == "create_file":
        path = Path(args["path"])
        if not path.parent.exists():
            return ("error", f"parent directory '{path.parent}' does not exist.")
        if path.exists():
            return ("error", f"'{path}' already exists.")
        path.touch()
        return ("ok", f"Created {path}.")

    if action == "delete_file":
        path = Path(args["path"])
        try:
            path.unlink()
        except OSError as e:
            return ("error", str(e))
        return ("ok", f"Deleted {path}.")

    return ("error", f"unknown action '{action}'.")


def execute(action: str, args: dict) -> tuple[str, str]:
    """Run a previously-``preview``ed action. Returns ``(status, detail)``
    with ``status`` one of ``'ok' | 'error'`` — never raises."""
    if sys.platform != "darwin":
        return ("error", f"execution not implemented for platform '{sys.platform}'.")
    try:
        return _execute_macos(action, args)
    except Exception as e:  # noqa: BLE001 - last-resort guard, this must never raise
        return ("error", str(e))
