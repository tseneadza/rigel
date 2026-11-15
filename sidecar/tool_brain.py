"""Rigel's brain with ToolBox tools — the tool-use loop for Claude and Ollama.

Same contract as ``brain._respond_via_provider``: produce a reply plus
Rigel's own four command intents (open/close app, create/delete file), which
still go through ``executor.py`` and its approval cards exactly as before.
The difference: before answering, the model may use ToolBox:

  * ``toolbox_need(intent)``  → ranked tools with input schemas
  * ``toolbox_call(tool, arguments)`` → runs it (servers start on demand;
    gated tools ask Tony through ``approvals.py`` and block until he answers)
  * ``respond(reply, commands)`` → the final answer; ends the loop

Every step is recorded as a ``ToolStep`` (returned to the desktop, which
folds them into a "used N tools" line, and logged to ``tool_calls``).

If ToolBox is unreachable the loop raises ``ToolBoxUnavailable`` and the
caller falls back to the plain brain with a note, so Rigel never fails
silently. ``max_steps`` caps need+call steps per reply (runaway guard);
after that the model must call ``respond``.
"""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
from dataclasses import asdict, dataclass

import anthropic

from sidecar import llm_providers, toolbox_client
from sidecar.toolbox_client import ToolBoxUnavailable

logger = logging.getLogger(__name__)

DEFAULT_MAX_STEPS = 5

TOOLBOX_SYSTEM = (
    " You also have ToolBox, a gateway to many tools on this Mac (system health, files, mail, git, "
    "weather, notes and more). For anything beyond Rigel's own four actions, first call toolbox_need "
    "with what you're trying to do, then toolbox_call with an exact tool name it returned and arguments "
    "matching its input_schema. Never guess tool names. Rigel's own actions (open_app, close_app, "
    "create_file, delete_file) never go through ToolBox: put them in respond.commands as before. "
    "Some ToolBox tools ask the user to approve first; toolbox_call waits for their answer. If a call was "
    "declined or not approved, say plainly that it wasn't done. If a tool errors, say what failed. "
    "Never state a fact or an outcome you didn't get from a tool result in this conversation: if you "
    "couldn't find or run the right tool, say so instead of guessing. "
    "When you're done, call respond. Replies may be spoken aloud: keep them short and natural, no "
    "markdown, no raw JSON."
)

NEED_TOOL = {
    "name": "toolbox_need",
    "description": "Find ToolBox tools for what you're trying to do. Returns tool names (server.tool), "
                   "descriptions and input schemas, best match first.",
    "input_schema": {
        "type": "object",
        "properties": {
            "intent": {"type": "string", "description": "What you're trying to do, in plain words."},
            "limit": {"type": "integer", "description": "Max tools to return (default 8)."},
        },
        "required": ["intent"],
    },
}
CALL_TOOL = {
    "name": "toolbox_call",
    "description": "Run a tool found with toolbox_need. `tool` is the full name (server.tool); "
                   "`arguments` must match its input_schema.",
    "input_schema": {
        "type": "object",
        "properties": {
            "tool": {"type": "string"},
            "arguments": {"type": "object"},
        },
        "required": ["tool"],
    },
}
NUDGE = ("You haven't run any tool yet, so nothing has happened. If one of the tools toolbox_need returned "
         "fits the request, call toolbox_call now with its exact name and arguments. Otherwise call respond "
         "and say you couldn't do it.")

RESPOND_TOOL = {
    "name": "respond",
    "description": "Give your final reply to the user, plus any of Rigel's own command intents.",
    "input_schema": llm_providers.RESPONSE_SCHEMA,
}


@dataclass
class ToolStep:
    kind: str                 # 'need' | 'call'
    tool: str                 # 'need' query text for need; server.tool for call
    arguments: dict
    status: str               # 'ok' | 'error' | 'declined' | 'expired'
    ms: int
    detail: str = ""          # short human note (no full output)
    approval: dict | None = None   # {status, answered_via} when one was asked

    def public(self) -> dict:
        return asdict(self)


class _Runner:
    """Executes need/call against ToolBox and records steps."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = toolbox_client.client()
        self.steps: list[ToolStep] = []
        # Tool names toolbox_need actually returned this turn. toolbox_call is
        # only allowed for these: small models (llama3.1:8b, seen live
        # 2026-11-15) skip need and invent names like "system health".
        self.known: set[str] = set()
        self.nudged = False

    def needs_nudge(self) -> bool:
        return bool(self.known) and not self.nudged and not any(s.kind == "call" for s in self.steps)

    def _need(self, intent: str, limit: int, started: float) -> tuple[str, bool]:
        text, is_error = self.client.need(self.base_url, _clean_intent(intent), limit)
        self.known.update(_need_names(text))
        self.steps.append(ToolStep(
            kind="need", tool=intent, arguments={"limit": limit},
            status="error" if is_error else "ok",
            ms=round((time.monotonic() - started) * 1000),
            detail=_need_summary(text),
        ))
        return text, is_error

    def run(self, name: str, args: dict) -> tuple[str, bool]:
        started = time.monotonic()
        if name == "toolbox_need":
            return self._need(str(args.get("intent") or ""), int(args.get("limit") or 8), started)
        if name == "toolbox_call":
            tool = str(args.get("tool") or "")
            arguments = _call_arguments(args)
            if tool not in self.known:
                text, is_error = self._need(tool.replace(".", " ").replace("_", " "), 5, started)
                if is_error:
                    return text, True
                same = [n for n in _need_names(text) if _norm(n) == _norm(tool)]
                if len(same) == 1:
                    # Only punctuation differs ("osa-system fs delete" vs
                    # "osa-system.fs.delete"): it's that tool. Approvals still apply.
                    tool = same[0]
                    started = time.monotonic()
                else:
                    return (f"{tool!r} is not a tool name you got from toolbox_need, so it was not run. "
                            f"I looked it up for you; these are the real matches. Call toolbox_call again "
                            f"with one of these exact `tool` names and arguments matching its input_schema:\n{text}"), True
            text, is_error, opened = self.client.call(self.base_url, tool, arguments)
            approval = None
            status = "error" if is_error else "ok"
            if opened:
                last = opened[-1]
                approval = {"status": last.status, "answered_via": last.answered_via, "id": last.id}
                if last.status == "declined":
                    status = "declined"
                elif last.status == "expired":
                    status = "expired"
            self.steps.append(ToolStep(
                kind="call", tool=tool, arguments=arguments, status=status,
                ms=round((time.monotonic() - started) * 1000),
                detail=_error_detail(text) if is_error else "", approval=approval,
            ))
            return text, is_error
        return f"Unknown tool {name!r}. Use toolbox_need, toolbox_call or respond.", True


def _error_detail(text: str) -> str:
    """Short error for the step chip. osa-system answers with a JSON body
    ({"error": "...", "declined": true}); its first line is just "{"."""
    try:
        data = json.loads(text)
        if isinstance(data, dict) and data.get("error"):
            return str(data["error"])[:160]
    except (ValueError, TypeError):
        pass
    return _first_line(text)


def _first_line(text: str, n: int = 160) -> str:
    line = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    return line[:n]


_PATHISH = re.compile(r"""(?:"[^"]*"|'[^']*'|\S*[/~\\]\S*)""")


def _clean_intent(intent: str) -> str:
    """ToolBox ranks tools against the words in `need`; a long file path or a
    quoted payload drowns the action words (live: 'delete file /Users/…/x.txt'
    matched 0 tools). Keep the words, drop path-like tokens and quotes."""
    cleaned = " ".join(_PATHISH.sub(" ", intent).split())
    words = cleaned.split()
    return " ".join(words[:16]) if words else intent[:120]


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _call_arguments(args: dict) -> dict:
    """The tool's arguments from a toolbox_call. Small models (llama3.1:8b,
    seen live) put them beside `tool` instead of inside `arguments`; fold any
    such stray keys in rather than failing validation."""
    arguments = dict(args.get("arguments")) if isinstance(args.get("arguments"), dict) else {}
    if isinstance(args.get("arguments"), str):
        try:
            parsed = json.loads(args["arguments"])
            if isinstance(parsed, dict):
                arguments = parsed
        except ValueError:
            pass
    for k, v in args.items():
        if k not in ("tool", "arguments") and k not in arguments:
            arguments[k] = v
    return arguments


def _text_tool_call(content: str) -> tuple[str, dict] | None:
    """A tool call the model wrote as text instead of making it — llama3.1
    sometimes replies with '{"name": "toolbox_call", "parameters": {...}}'.
    Only our own three tool names are accepted."""
    start = content.find("{")
    if start < 0:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(content[start:])
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    name = data.get("name") or (data.get("function") or {}).get("name")
    params = data.get("parameters", data.get("arguments", {}))
    if name in ("toolbox_need", "toolbox_call", "respond") and isinstance(params, dict):
        return name, params
    return None


def _need_names(text: str) -> list[str]:
    try:
        data = json.loads(text)
        names = [m.get("tool") or m.get("name") for m in data.get("matches", [])]
    except (ValueError, AttributeError, TypeError):
        return []
    return [n for n in names if isinstance(n, str) and n]


def _need_summary(text: str) -> str:
    names = _need_names(text)
    return f"{len(names)} tools" + (f": {', '.join(names[:3])}" if names else "")


# ── Claude ───────────────────────────────────────────────────────────────

def _claude_loop(text: str, model: str, runner: _Runner, max_steps: int) -> tuple[str, list[dict]]:
    if model not in llm_providers.CLAUDE_MODELS:
        raise llm_providers.LLMError(f"unknown Claude model: {model!r}")
    client = llm_providers.anthropic_client()
    messages: list[dict] = [{"role": "user", "content": text}]
    system = llm_providers.SYSTEM_PROMPT + TOOLBOX_SYSTEM
    used = 0
    for _ in range(max_steps + 2):
        tools = [NEED_TOOL, CALL_TOOL, RESPOND_TOOL] if used < max_steps else [RESPOND_TOOL]
        choice = {"type": "any"} if used < max_steps else {"type": "tool", "name": "respond"}
        try:
            response = client.messages.create(
                model=model, max_tokens=1024, system=system,
                tools=tools, tool_choice=choice, messages=messages,
            )
        except anthropic.APIError as e:
            raise llm_providers.LLMError(f"Claude error: {e}") from e
        except TypeError as e:
            raise llm_providers.LLMError(f"Claude credentials not configured: {e}") from e

        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name == "respond":
                if runner.needs_nudge() and used < max_steps:
                    runner.nudged = True
                    results.append({"type": "tool_result", "tool_use_id": block.id,
                                    "content": "Not sent. " + NUDGE, "is_error": True})
                    continue
                return llm_providers._parse_response_json(json.dumps(block.input))
            out, is_error = runner.run(block.name, dict(block.input or {}))
            used += 1
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": out, "is_error": is_error})
        if not results:
            # Text with no tool call (shouldn't happen with tool_choice=any).
            reply = " ".join(b.text for b in response.content if b.type == "text").strip()
            return reply or "Done.", []
        messages.append({"role": "user", "content": results})
    raise llm_providers.LLMError("tool loop did not finish")


# ── Ollama ───────────────────────────────────────────────────────────────

def _ollama_tool(t: dict) -> dict:
    return {"type": "function", "function": {
        "name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}


def ollama_supports_tools(model: str, host: str) -> bool:
    try:
        info = llm_providers._ollama_request(host, "/api/show", {"model": model}, timeout=5.0)
    except Exception:  # noqa: BLE001
        return False
    return "tools" in (info.get("capabilities") or [])


def _ollama_loop(text: str, model: str, host: str, runner: _Runner, max_steps: int) -> tuple[str, list[dict]]:
    system = llm_providers.SYSTEM_PROMPT + TOOLBOX_SYSTEM + (
        " To answer, call respond with reply and commands (args_json is a JSON-encoded string)."
    )
    messages: list[dict] = [{"role": "system", "content": system}, {"role": "user", "content": text}]
    used = 0
    for _ in range(max_steps + 2):
        tools = [NEED_TOOL, CALL_TOOL, RESPOND_TOOL] if used < max_steps else [RESPOND_TOOL]
        body = {"model": model, "stream": False, "messages": messages, "tools": [_ollama_tool(t) for t in tools]}
        try:
            result = llm_providers._ollama_request(host, "/api/chat", body, timeout=60.0)
        except (urllib.error.URLError, TimeoutError) as e:
            raise llm_providers.LLMError(f"Ollama unreachable at {host}: {e}") from e
        msg = result.get("message") or {}
        calls = msg.get("tool_calls") or []
        messages.append({"role": "assistant", "content": msg.get("content", ""), "tool_calls": calls})
        if not calls:
            content = (msg.get("content") or "").strip()
            as_text = _text_tool_call(content)
            if as_text is not None:
                calls = [{"function": {"name": as_text[0], "arguments": as_text[1]}}]
                messages[-1]["tool_calls"] = calls
            elif runner.needs_nudge():
                # Live (llama3.1:8b): found the tool, then replied "I've called
                # it" without calling. One push to act or admit it can't.
                runner.nudged = True
                messages.append({"role": "user", "content": NUDGE})
                continue
            else:
                try:
                    return llm_providers._parse_response_json(content)
                except llm_providers.LLMError:
                    return content or "Done.", []
        for c in calls:
            fn = c.get("function") or {}
            name = fn.get("name", "")
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            if name == "respond":
                return llm_providers._parse_response_json(json.dumps(args))
            out, is_error = runner.run(name, args)
            used += 1
            messages.append({"role": "tool", "tool_name": name, "content": out})
    raise llm_providers.LLMError("tool loop did not finish")


# ── entry point ──────────────────────────────────────────────────────────

def respond(text: str, llm_config: dict, toolbox_config: dict) -> tuple[str, list[dict], list[ToolStep]]:
    """Raises ToolBoxUnavailable (→ caller falls back), LLMError (→ caller
    falls back to the stub), or returns (reply, commands, steps)."""
    base_url = toolbox_client.discover_base_url(toolbox_config.get("url"))
    toolbox_client.client().ping(base_url)  # fail fast, before spending an LLM call
    runner = _Runner(base_url)
    max_steps = max(1, min(int(toolbox_config.get("max_steps") or DEFAULT_MAX_STEPS), 15))
    provider = llm_config.get("provider")
    try:
        if provider == "claude":
            reply, commands = _claude_loop(text, llm_config["claude_model"], runner, max_steps)
        elif provider == "ollama":
            reply, commands = _ollama_loop(
                text, llm_config["ollama_model"],
                llm_config.get("ollama_host", llm_providers.DEFAULT_OLLAMA_HOST), runner, max_steps,
            )
        else:
            raise llm_providers.LLMError(f"provider {provider!r} has no tool use")
    except ToolBoxUnavailable as e:
        e.steps = runner.steps  # type: ignore[attr-defined]
        raise
    return _sanitize_reply(reply, commands, runner.steps), commands, runner.steps


_LEAK = re.compile(r"(?:\b(?:respond|toolbox_call|toolbox_need)\s*\(|\{\s*\"(?:name|tool|reply|commands)\"\s*:)")
_FALSE_WAIT = re.compile(r"waiting on your approval|check the console", re.I)
_CLAIMED_ACTION = re.compile(
    r"\bI(?:'ve| have)? (?:called|run|ran|executed|deleted|sent|created|moved|checked)\b|\b[\w-]+\.[\w.]+ with\b", re.I)


def _sanitize_reply(reply: str, commands: list[dict], steps: list[ToolStep]) -> str:
    """Guard the spoken reply against small-model leaks (live, llama3.1:8b:
    'respond(commands=[...])' in the text, and 'waiting on your approval'
    for a ToolBox call that had already run). Drops leaked tool-call text;
    if what's left is empty or claims a pending approval that doesn't
    exist, answer with a factual summary of the steps instead."""
    lines = [ln for ln in (reply or "").splitlines() if not _LEAK.search(ln)]
    cleaned = "\n".join(lines).strip()
    calls = [s for s in steps if s.kind == "call"]
    if not calls and not commands and _CLAIMED_ACTION.search(cleaned):
        # Claims something ran when nothing did (live, llama3.1:8b).
        return "I found a tool for that but didn't actually run it, so nothing has changed. Ask me again?"
    if cleaned and not (not commands and _FALSE_WAIT.search(cleaned) and calls):
        return cleaned
    if not calls:
        return cleaned or "I couldn't find the right tool for that."
    return " ".join(_step_sentence(s) for s in calls)


def _step_sentence(s: ToolStep) -> str:
    name = s.tool.split(".", 1)[-1].replace(".", " ").replace("_", " ")
    via = (s.approval or {}).get("answered_via")
    if s.status == "ok":
        return f"Done: {name} ran" + (f" after you approved it by {via}." if via else ".")
    if s.status == "declined":
        return f"I didn't run {name}, since it wasn't approved."
    if s.status == "expired":
        return f"{name} wasn't run: the server stopped waiting for your answer."
    return f"{name} failed" + (f": {s.detail}" if s.detail else ".")
