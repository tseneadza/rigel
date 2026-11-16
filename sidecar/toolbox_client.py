"""Rigel's connection to ToolBox, Tony's MCP gateway (~/Codehome/ToolBox).

ToolBox exposes three MCP tools to agents: ``need(intent)``, ``call(tool,
arguments)`` and ``request(capability, reason)``. Rigel's brain uses the
first two (see ``tool_brain.py``). This module owns one long-lived MCP
session to the shared ToolBox service, identified as ``rigel`` (MCP
clientInfo), on a private asyncio loop in a daemon thread, and gives the
rest of the (synchronous) sidecar plain blocking functions.

Approvals: some servers behind ToolBox (osa-system's gated tools) ask the
human through MCP elicitation. ToolBox forwards that request to us; we hand
it to ``approvals.py``, which parks it until Tony answers on the console
card or by voice. There is deliberately no Rigel-side timeout on that wait
(Tony's call, 2026-11-15) — but the *server* may give up on its own
(osa-system declines after 120 s), in which case the call returns and the
still-open approval is marked expired.

Where ToolBox is: ``~/.toolbox/service.json`` (written by ``toolbox serve``,
holds host + port), falling back to 127.0.0.1:8795. ``toolbox_config.url``
overrides both.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import urllib.request
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from sidecar import approvals

logger = logging.getLogger(__name__)

CLIENT_NAME = "rigel"
CLIENT_VERSION = "0.1.0"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8795
CONNECT_TIMEOUT_S = 5.0
NEED_TIMEOUT_S = 30.0
# Characters of a tool result handed back to the LLM. Tool outputs (a mail
# search, a directory listing) can be huge; the brain needs the gist.
MAX_RESULT_CHARS = 8000


class ToolBoxUnavailable(Exception):
    """ToolBox isn't reachable (not running, wrong address, refused)."""


def _toolbox_home() -> Path:
    return Path(os.getenv("TOOLBOX_HOME", Path.home() / ".toolbox")).expanduser()


def discover_base_url(override: str | None = None) -> str:
    """``http://host:port`` of the running ToolBox service."""
    if override:
        return override.rstrip("/").removesuffix("/mcp")
    try:
        info = json.loads((_toolbox_home() / "service.json").read_text())
        return f"http://{info.get('host') or DEFAULT_HOST}:{int(info['port'])}"
    except (OSError, ValueError, KeyError, TypeError):
        return f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"


def fetch_status(base_url: str, timeout: float = 2.0) -> dict:
    """ToolBox's own ``/status`` (servers, tool counts, states). Raises
    ToolBoxUnavailable if it can't be read."""
    host = base_url.split("://", 1)[-1]
    req = urllib.request.Request(base_url + "/status", headers={"Host": host})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001 — any failure means "not reachable"
        raise ToolBoxUnavailable(f"ToolBox unreachable at {base_url}: {e}") from e


def result_to_text(result: Any) -> tuple[str, bool]:
    """Flatten an MCP CallToolResult into (text, is_error) for the LLM."""
    is_error = bool(getattr(result, "is_error", False))
    parts: list[str] = []
    structured = getattr(result, "structured_content", None)
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
        else:
            parts.append(f"[{getattr(block, 'type', 'content')} omitted]")
    if not parts and structured is not None:
        parts.append(json.dumps(structured, default=str))
    text = "\n".join(parts) or "(no output)"
    if len(text) > MAX_RESULT_CHARS:
        text = text[:MAX_RESULT_CHARS] + f"\n… (truncated, {len(text) - MAX_RESULT_CHARS} more chars)"
    return text, is_error


def _parse_tool_error(text: str) -> bool:
    """osa-system reports a declined/failed gated call as a JSON body with
    'error' rather than an MCP error flag — treat that as an error too."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return False
    return isinstance(data, dict) and ("error" in data) and not data.get("ok", False)


class ToolBoxClient:
    """One MCP session to ToolBox, on its own event loop thread."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, name="rigel-toolbox", daemon=True)
        self._thread.start()
        self._session = None
        self._session_task: asyncio.Task | None = None
        self._url: str | None = None
        self._connect_lock: asyncio.Lock | None = None
        # Stack of the calls currently waiting on ToolBox, so an elicitation
        # (which arrives on the session's receive task, not the caller's)
        # can be attributed to a tool. Same approach as ToolBox's bridge.
        self._active_calls: list[str] = []

    # ── loop plumbing ────────────────────────────────────────────────────

    def _run(self, coro, timeout: float | None):
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout)

    async def _ensure(self, url: str):
        if self._connect_lock is None:
            self._connect_lock = asyncio.Lock()
        async with self._connect_lock:
            alive = self._session is not None and self._session_task is not None and not self._session_task.done()
            if alive and self._url == url:
                return self._session
            if self._session_task is not None and not self._session_task.done():
                self._session_task.cancel()
            ready: asyncio.Future = self._loop.create_future()
            self._session_task = asyncio.create_task(self._hold(url, ready))
            try:
                await asyncio.wait_for(asyncio.shield(ready), CONNECT_TIMEOUT_S)
            except asyncio.TimeoutError as e:
                self._session_task.cancel()
                raise ToolBoxUnavailable(f"ToolBox at {url} didn't answer within {CONNECT_TIMEOUT_S:.0f}s") from e
            self._url = url
            return self._session

    async def _hold(self, url: str, ready: asyncio.Future) -> None:
        import httpx2
        from mcp import ClientSession, types
        from mcp.client.streamable_http import streamable_http_client
        from mcp.shared._httpx_utils import MCP_DEFAULT_TIMEOUT, create_mcp_http_client

        try:
            async with AsyncExitStack() as stack:
                # No read timeout on the stream: an approval can legitimately
                # keep a call open for as long as Tony takes to answer.
                http = create_mcp_http_client(timeout=httpx2.Timeout(MCP_DEFAULT_TIMEOUT, read=None))
                await stack.enter_async_context(http)
                streams = await stack.enter_async_context(streamable_http_client(url + "/mcp", http_client=http))
                read, write = streams[0], streams[1]
                session = await stack.enter_async_context(
                    ClientSession(
                        read, write,
                        elicitation_callback=self._on_elicit,
                        client_info=types.Implementation(name=CLIENT_NAME, version=CLIENT_VERSION),
                    )
                )
                await session.initialize()
                self._session = session
                ready.set_result(None)
                await asyncio.Event().wait()  # keep the session open until cancelled
        except BaseException as e:  # noqa: BLE001
            if not ready.done():
                ready.set_exception(ToolBoxUnavailable(f"ToolBox unreachable at {url}: {e!r}"))
            logger.warning("ToolBox session closed: %r", e)
        finally:
            self._session = None

    async def _on_elicit(self, context, params):
        from mcp import types

        if getattr(params, "mode", "form") != "form":
            return types.ElicitResult(action="decline")
        tool = self._active_calls[-1] if self._active_calls else "unknown tool"
        schema = getattr(params, "requested_schema", None) or {}
        approval = approvals.open_approval(tool=tool, message=params.message, schema=schema)
        logger.info("ToolBox approval %s opened for %s", approval.id, tool)
        decision = await self._loop.run_in_executor(None, approval.wait)
        if decision != "approve":
            return types.ElicitResult(action="decline")
        return types.ElicitResult(action="accept", content=approvals.accept_content(schema))

    # ── public, blocking API ────────────────────────────────────────────

    def need(self, url: str, intent: str, limit: int = 8) -> tuple[str, bool]:
        async def go():
            session = await self._ensure(url)
            return await session.call_tool("need", {"intent": intent, "limit": limit})
        try:
            return result_to_text(self._run(go(), NEED_TIMEOUT_S))
        except ToolBoxUnavailable:
            raise
        except Exception as e:  # noqa: BLE001
            raise ToolBoxUnavailable(f"ToolBox need() failed: {e!r}") from e

    def call(self, url: str, tool: str, arguments: dict | None) -> tuple[str, bool, list[approvals.Approval]]:
        """Run ``tool`` through ToolBox. Blocks for as long as an approval is
        open. Returns (text, is_error, approvals opened during this call)."""
        before = approvals.snapshot_ids()

        async def go():
            session = await self._ensure(url)
            self._active_calls.append(tool)
            try:
                return await session.call_tool("call", {"tool": tool, "arguments": arguments or {}})
            finally:
                self._active_calls.remove(tool)
        try:
            result = self._run(go(), None)
        except ToolBoxUnavailable:
            raise
        except Exception as e:  # noqa: BLE001
            raise ToolBoxUnavailable(f"ToolBox call() failed: {e!r}") from e
        finally:
            opened = approvals.opened_since(before)
            # The server stopped waiting (e.g. osa-system's own 120 s limit)
            # before anyone answered: close the card rather than leave it
            # promising an action that can no longer happen.
            for a in opened:
                a.expire_if_pending(f"{tool.split('.')[0]} stopped waiting for an answer.")
        text, is_error = result_to_text(result)
        return text, (is_error or _parse_tool_error(text)), opened

    def ping(self, url: str) -> None:
        self._run(self._ensure(url), CONNECT_TIMEOUT_S + 1)


_CLIENT: ToolBoxClient | None = None
_CLIENT_LOCK = threading.Lock()


def client() -> ToolBoxClient:
    global _CLIENT
    with _CLIENT_LOCK:
        if _CLIENT is None:
            _CLIENT = ToolBoxClient()
        return _CLIENT


def status(config: dict) -> dict:
    """Snapshot for Settings and the console badge."""
    if not config.get("enabled", True):
        return {"state": "disabled"}
    url = discover_base_url(config.get("url"))
    started = time.monotonic()
    try:
        st = fetch_status(url)
    except ToolBoxUnavailable as e:
        return {"state": "offline", "url": url, "detail": str(e)}
    servers = st.get("servers") or {}
    return {
        "state": "connected",
        "url": url,
        "servers": len(servers),
        "tools": sum(int(s.get("tools") or 0) for s in servers.values()),
        "latency_ms": round((time.monotonic() - started) * 1000),
    }
