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

  ``is_whitelisted(action, args, whitelist)`` — check a *previewed* action's
                                 resolved args against the user's whitelist
                                 (``app.py``'s ``whitelist_config`` setting).
                                 ``app.py`` calls ``execute`` immediately
                                 instead of waiting for approval when this
                                 returns True.

Six actions share that contract: the original four (``open_app``,
``close_app``, ``create_file``, ``delete_file``), ``app_action`` — a
per-app command produced by one of the handlers in ``sidecar/handlers/``
(``{"app_id": ..., "tool": ..., "tool_args": {...}}``) — and
``click_menu_item`` — a dynamic app-menu click (Slice 4 of App Menu
Actions, ``docs/proposals/menu-actions.md``) produced by ``brain.py``'s
own fuzzy-match fallback rather than any handler
(``{"app": ..., "menu_path": [...]}}``). Where the first four run through
``_execute_macos`` directly, ``app_action``/``click_menu_item`` dispatch to
``sidecar/handlers/``: the matched handler's own ``execute_tool`` for the
former, ``menu_actions.click_menu_item`` for the latter. This module still
owns validating the args (in ``preview``) and the whitelist/execute
plumbing around both, same as any other action —
``click_menu_item``'s whitelist check additionally consults
``menu_actions.is_dangerous()`` first, and forces approval regardless of
whitelist state when it matches (see ``is_whitelisted``).

macOS only for now — other platforms raise ``NotImplementedError``, which
``execute`` turns into an ordinary ``"error"`` status rather than a crash.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from sidecar.handlers import menu_actions, registry

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

    if action == "app_action":
        app_id = str(args.get("app_id", "")).strip()
        tool = str(args.get("tool", "")).strip()
        if not app_id or not tool:
            raise UnsafeCommandError("app_action missing app_id/tool.")
        handler = registry.get(app_id)
        if handler is None:
            raise UnsafeCommandError(f"no handler registered for app '{app_id}'.")
        if tool not in {t["name"] for t in handler.tools}:
            raise UnsafeCommandError(f"'{tool}' is not a recognized action for {handler.display_name}.")
        tool_args = args.get("tool_args")
        return {"app_id": app_id, "tool": tool, "tool_args": tool_args if isinstance(tool_args, dict) else {}}

    if action == "click_menu_item":
        app = str(args.get("app", "")).strip()
        menu_path = args.get("menu_path")
        if not app:
            raise UnsafeCommandError("no app name given.")
        if not isinstance(menu_path, list) or not menu_path or not all(
            isinstance(segment, str) and segment.strip() for segment in menu_path
        ):
            raise UnsafeCommandError("menu_path must be a non-empty list of menu item names.")
        # No further resolution needed, unlike app_action's tool-name check
        # against a handler's declared tools — menu_path was already
        # validated against a live discover_menu() walk when brain.py
        # built it (see docs/proposals/menu-actions.md's Slice 4 section
        # for why re-verifying here isn't worth it: a stale path surfaces
        # as an ordinary execution error either way).
        return {"app": app, "menu_path": [segment.strip() for segment in menu_path]}

    raise UnsafeCommandError(f"unknown action '{action}'.")


def is_whitelisted(action: str, resolved_args: dict, whitelist: dict | None) -> bool:
    """Check *previewed* (already-resolved) ``args`` against the user's
    per-action whitelist: ``{action: {"all": bool, "targets": [str, ...]}}``.

    ``"all"`` matches any target for that action; otherwise the target
    (an app name for open/close, a resolved absolute path for file actions)
    must exactly match one of ``"targets"``, case-insensitively.

    ``app_action`` is keyed differently — per app, not per global action —
    since "auto-approve Chrome's new-tab" shouldn't also auto-approve VS
    Code opening arbitrary folders. Its shape is
    ``whitelist["app_action"] = {app_id: {"all": bool, "tools": [str, ...]}}``.

    ``click_menu_item`` is keyed the same way, per app
    (``whitelist["click_menu_item"] = {app: {"all": bool, "menu_paths":
    [[str, ...], ...]}}``), but with one override no other action has:
    ``menu_actions.is_dangerous(menu_path)`` is checked *first*, and a
    match returns ``False`` unconditionally — a dangerous-sounding item
    (delete, quit, empty trash, ...) always requires approval, even with
    ``all: true`` set for that app. Nothing else in this whitelist can be
    overridden this way; menu actions are the one case where discovering
    an item's real label at runtime means the whitelist can't have vetted
    it in advance the way a fixed action/tool name can be.
    """
    if action == "click_menu_item":
        menu_path = resolved_args.get("menu_path") or []
        if menu_actions.is_dangerous(menu_path):
            return False
        app = str(resolved_args.get("app") or "")
        entry = ((whitelist or {}).get("click_menu_item") or {}).get(app) or {}
        if entry.get("all"):
            return True
        whitelisted_paths = entry.get("menu_paths") or []
        return list(menu_path) in [list(p) for p in whitelisted_paths]

    if action == "app_action":
        app_id = str(resolved_args.get("app_id") or "")
        tool = str(resolved_args.get("tool") or "")
        entry = ((whitelist or {}).get("app_action") or {}).get(app_id) or {}
        if entry.get("all"):
            return True
        tools = entry.get("tools") or []
        return tool in set(tools)

    entry = (whitelist or {}).get(action) or {}
    if entry.get("all"):
        return True
    target = str(resolved_args.get("target") or resolved_args.get("path") or "")
    targets = entry.get("targets") or []
    return target.lower() in {str(t).lower() for t in targets}


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

    if action == "app_action":
        handler = registry.get(args["app_id"])
        if handler is None:
            return ("error", f"no handler registered for app '{args['app_id']}'.")
        return handler.execute_tool(args["tool"], args.get("tool_args") or {})

    if action == "click_menu_item":
        return menu_actions.click_menu_item(args["app"], args["menu_path"])

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
