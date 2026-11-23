"""ToolBox approvals — the human-in-the-loop half of MCP elicitation.

When a server behind ToolBox wants permission (osa-system's gated tools),
``toolbox_client`` opens an ``Approval`` here and blocks on it. The desktop
polls ``pending()``, shows the card, speaks ``spoken``, and answers through
``answer()`` (click) or ``interpret()`` (voice / free text).

Safety rules (approval-gate-validation):
  * The only way to approve is an explicit answer: a click on Approve, or an
    utterance that ``interpret()`` classifies as a clear yes. No default
    action, no auto-approve, no whitelist for ToolBox tools.
  * Anything ambiguous is ``unclear``, never ``approve`` — Rigel asks a
    follow-up question instead (Tony, 2026-11-15: "be flexible, and ask
    follow-up questions if you're not sure of the intent").
  * A mixed answer ("yes— no wait") is unclear, and negation wins over any
    keyword match for approval only if it's unambiguous.
  * No Rigel-side timeout (Tony's call). A server may still give up on its
    own; the approval is then marked ``expired`` and can't be answered.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

_LOCK = threading.Lock()
_APPROVALS: dict[str, "Approval"] = {}
_ORDER: list[str] = []
_KEEP = 50  # resolved approvals kept around for the desktop to read back

# Audit trail: every approval's open, answer and expiry is logged, so a
# decision can always be traced to how it was given (click, voice or typed).
logger = logging.getLogger("rigel.approvals")


@dataclass
class Approval:
    id: str
    tool: str
    message: str
    schema: dict
    spoken: str
    created_at: str
    status: str = "pending"        # pending | approved | declined | expired
    answered_via: str | None = None  # click | voice | typed
    detail: str | None = None
    follow_ups: int = 0
    _event: threading.Event = field(default_factory=threading.Event, repr=False)

    def wait(self) -> str:
        """Block until answered or expired. Returns 'approve' only on approval."""
        self._event.wait()
        return "approve" if self.status == "approved" else "decline"

    def resolve(self, decision: str, via: str) -> bool:
        with _LOCK:
            if self.status != "pending":
                return False
            self.status = "approved" if decision == "approve" else "declined"
            self.answered_via = via
        logger.info("approval %s %s via=%s tool=%s", self.id, self.status, via, self.tool)
        self._event.set()
        return True

    def expire_if_pending(self, detail: str) -> None:
        with _LOCK:
            if self.status != "pending":
                return
            self.status = "expired"
            self.detail = detail
        logger.info("approval %s expired tool=%s: %s", self.id, self.tool, detail)
        self._event.set()

    def public(self) -> dict:
        return {
            "id": self.id,
            "tool": self.tool,
            "server": self.tool.split(".", 1)[0],
            "message": self.message,
            "spoken": self.spoken,
            "created_at": self.created_at,
            "status": self.status,
            "answered_via": self.answered_via,
            "detail": self.detail,
        }


# ── creation / lookup ──────────────────────────────────────────────────────

def _spoken_summary(tool: str, message: str) -> str:
    """One sentence Rigel says out loud. osa-system's message is
    'osa-system wants to run: fs.delete [irreversible]' then '  key: value'
    lines; we keep the action and the first argument."""
    lines = [ln.strip() for ln in message.splitlines() if ln.strip()]
    short_tool = tool.split(".", 1)[-1].replace("_", " ").replace(".", " ")
    risk = ""
    m = re.search(r"\[(\w[\w-]*)\]", lines[0]) if lines else None
    if m:
        risk = f" It's {m.group(1)}."
    target = ""
    for ln in lines[1:]:
        if ":" in ln and not ln.lower().startswith("details"):
            target = ln.split(":", 1)[1].strip()
            break
    if len(target) > 80:
        target = target[:77] + "…"
    what = f"{short_tool} on {target}" if target else short_tool
    return f"I need your OK to run {what}.{risk} Should I go ahead?"


def open_approval(tool: str, message: str, schema: dict) -> Approval:
    a = Approval(
        id=uuid.uuid4().hex[:10],
        tool=tool,
        message=message,
        schema=schema or {},
        spoken=_spoken_summary(tool, message),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    logger.info("approval %s opened tool=%s", a.id, a.tool)
    with _LOCK:
        _APPROVALS[a.id] = a
        _ORDER.append(a.id)
        while len(_ORDER) > _KEEP:
            old = _APPROVALS.get(_ORDER[0])
            if old is not None and old.status == "pending":
                break
            _APPROVALS.pop(_ORDER.pop(0), None)
    return a


def get(approval_id: str) -> Approval | None:
    with _LOCK:
        return _APPROVALS.get(approval_id)


def pending() -> list[dict]:
    with _LOCK:
        return [_APPROVALS[i].public() for i in _ORDER if _APPROVALS[i].status == "pending"]


def snapshot_ids() -> set[str]:
    with _LOCK:
        return set(_ORDER)


def opened_since(before: set[str]) -> list[Approval]:
    with _LOCK:
        return [_APPROVALS[i] for i in _ORDER if i not in before]


def accept_content(schema: dict) -> dict:
    """Fill the server's requested form for an approval. Every boolean field
    becomes True (osa-system asks for {approve: boolean}); other fields take
    their schema default if one exists. Only ever called after an explicit yes."""
    content: dict = {}
    for name, prop in ((schema or {}).get("properties") or {}).items():
        if not isinstance(prop, dict):
            continue
        if prop.get("type") == "boolean":
            content[name] = True
        elif "default" in prop:
            content[name] = prop["default"]
    return content


# ── interpreting a spoken / typed answer ───────────────────────────────────

_YES = re.compile(
    r"^(?:yes|yeah|yep|yup|ya|sure|ok|okay|alright|all right|affirmative|correct|"
    r"approve|approved|confirm|confirmed|go ahead|go for it|do it|proceed|please do|"
    r"absolutely|definitely|of course|sounds good|that's fine|that is fine|fine|"
    r"yes please|yes do it|yes go ahead)\b",
    re.I,
)
_NO = re.compile(
    r"\b(?:no|nope|nah|don't|do not|stop|cancel|decline|deny|denied|never mind|nevermind|"
    r"abort|negative|not now|leave it|forget it|skip it|reject)\b",
    re.I,
)
# "hold on" / "wait" usually mean "let me think", not "no": ask again.
_HEDGE = re.compile(
    r"\b(?:maybe|i guess|i think|not sure|perhaps|probably|hmm+|um+|uh+|hold on|wait|let me think)\b|\?$", re.I)


def _normalize(text: str) -> str:
    t = re.sub(r"[.!,]+", " ", text.strip()).strip()
    return re.sub(r"^(?:rigel|um+|uh+|so|well)\s+", "", t, flags=re.I).strip()


# Grunts, hums and fillers. Speech-to-text turns room noise and TV sound into
# these ("Mm-hmm", "Ugh"), so they must never reach the language model.
_FILLER_WORD = re.compile(
    r"^(?:m+|h+m+|m+h+m+|mm-?hmm+|uh-?huh|u+h+|u+m+|a+h+|o+h+|e+h+|e+r+|u+g+h+|huh|hm+)$", re.I)


def _is_filler(text: str) -> bool:
    words = [w for w in re.split(r"[\s.,!?;:…\-]+", text.strip()) if w and not re.fullmatch(r"[\W_]+", w)]
    return not words or all(_FILLER_WORD.fullmatch(w) for w in words)


def _clear_yes_start(text: str) -> bool:
    """True only for an answer that starts with a yes word and has no
    negation and no hedge. The only shape the language model may approve."""
    return bool(_YES.search(_normalize(text))) and not _NO.search(text) and not _HEDGE.search(text.strip())


def _keyword_decision(text: str) -> str:
    t = _normalize(text)
    if not t:
        return "unclear"
    yes = bool(_YES.search(t))
    no = bool(_NO.search(t))
    if _HEDGE.search(text.strip()):
        return "unclear"
    if yes and not no:
        return "approve"
    if no and not yes:
        return "decline"
    return "unclear"


_CLASSIFY_PROMPT = (
    "You decide whether a user approved an action. Rigel asked: {question!r}. "
    "The user answered (speech-to-text, may have errors): {answer!r}. "
    "Return JSON {{\"decision\": \"approve\"|\"decline\"|\"unclear\", \"follow_up\": \"<short question or empty>\"}}. "
    "Only 'approve' if the answer clearly and unambiguously agrees. Any doubt, hedging, a question back, "
    "or an unrelated reply is 'unclear', and then follow_up is one short spoken question that helps them answer "
    "(e.g. restate what will happen and ask yes or no). 'decline' if they refuse or want to stop."
)


def _llm_decision(question: str, answer: str, llm_config: dict | None) -> tuple[str, str]:
    from sidecar import llm_providers  # local import: keep this module light for tests

    provider = (llm_config or {}).get("provider", "stub")
    prompt = _CLASSIFY_PROMPT.format(question=question, answer=answer)
    try:
        if provider == "claude":
            raw = llm_providers.claude_json(prompt, llm_config["claude_model"], _DECISION_SCHEMA)
        elif provider == "ollama":
            raw = llm_providers.ollama_json(
                prompt, llm_config["ollama_model"],
                llm_config.get("ollama_host", llm_providers.DEFAULT_OLLAMA_HOST),
            )
        else:
            return "unclear", ""
        data = json.loads(raw)
    except Exception:  # noqa: BLE001 — a classifier failure must never approve
        return "unclear", ""
    decision = data.get("decision") if isinstance(data, dict) else None
    if decision not in ("approve", "decline", "unclear"):
        decision = "unclear"
    follow_up = str(data.get("follow_up") or "") if isinstance(data, dict) else ""
    return decision, follow_up


_DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["approve", "decline", "unclear"]},
        "follow_up": {"type": "string"},
    },
    "required": ["decision", "follow_up"],
    "additionalProperties": False,
}


def interpret(approval: Approval, text: str, llm_config: dict | None, via: str = "voice") -> dict:
    """Classify a free-form answer. Applies it if clear; otherwise returns a
    follow-up question. Keyword match first (fast, deterministic); the LLM
    is consulted only when keywords can't decide. A keyword 'approve' is
    trusted only for short answers — a long sentence goes to the LLM."""
    decision = _keyword_decision(text)
    logger.info("approval %s heard via=%s text=%r keyword=%s", approval.id, via, text, decision)
    follow_up = ""
    if decision == "approve" and len(text.split()) > 6:
        decision = "unclear"
    if decision == "unclear" and not _is_filler(text):
        decision, follow_up = _llm_decision(approval.spoken, text, llm_config)
        # Approval is for a clear yes only. A model that says "approve" about
        # a grunt, noise or a hedged or mixed answer is downgraded to unclear.
        if decision == "approve" and not _clear_yes_start(text):
            decision = "unclear"
    if decision in ("approve", "decline"):
        applied = approval.resolve(decision, via)
        if not applied:
            return {"decision": "closed", "status": approval.status, "approval": approval.public()}
        return {"decision": decision, "status": approval.status, "approval": approval.public()}
    approval.follow_ups += 1
    # Rigel's own wording, not the model's: a small model's follow-up was
    # garbled live ("That means you'll delete a file permanently"). The
    # model only classifies; the question always restates exactly what
    # will run, which is the one thing the user needs to decide.
    follow_up = (
        "Sorry, I didn't catch that. " + approval.spoken
        if approval.follow_ups == 1
        else "I still need a clear yes or no. " + approval.spoken
    )
    return {"decision": "unclear", "follow_up": follow_up, "approval": approval.public()}
