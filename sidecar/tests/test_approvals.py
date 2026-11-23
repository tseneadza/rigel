"""Safety tests for ToolBox approvals (approval-gate-validation):
nothing approves unless the answer is a clear yes; anything unclear asks a
follow-up; closed approvals can't be reopened."""
import threading

import pytest

from sidecar import approvals


def _new(tool="osa-system.fs.delete"):
    msg = "osa-system wants to run: fs.delete  [irreversible]\n  path: /tmp/x.txt"
    return approvals.open_approval(tool, msg, {"type": "object", "properties": {"approve": {"type": "boolean"}}})


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    # The LLM fallback must never be needed for these; make it say "unclear".
    monkeypatch.setattr(approvals, "_llm_decision", lambda q, a, c: ("unclear", ""))


@pytest.mark.parametrize("text", ["yes", "Yes.", "yeah", "yep go ahead", "sure", "okay", "go ahead",
                                  "do it", "approve", "yes please", "Rigel, yes"])
def test_clear_yes_approves(text):
    a = _new()
    r = approvals.interpret(a, text, None)
    assert r["decision"] == "approve" and a.status == "approved" and a.answered_via == "voice"


@pytest.mark.parametrize("text", ["no", "nope", "don't", "stop", "cancel", "never mind", "no don't do that",
                                  "abort", "not now"])
def test_clear_no_declines(text):
    a = _new()
    r = approvals.interpret(a, text, None)
    assert r["decision"] == "decline" and a.status == "declined"


@pytest.mark.parametrize("text", ["maybe", "yes? ", "I think so", "yes, no wait", "what is it deleting",
                                  "um", "", "purple", "yes I guess", "hold on", "wait",
                                  "yes and also could you tell me what the weather is like today"])
def test_unclear_never_approves_and_asks_follow_up(text):
    a = _new()
    r = approvals.interpret(a, text, None)
    assert r["decision"] == "unclear"
    assert a.status == "pending"
    assert r["follow_up"]


def test_second_follow_up_is_firmer():
    a = _new()
    first = approvals.interpret(a, "hmm", None)["follow_up"]
    second = approvals.interpret(a, "hmm", None)["follow_up"]
    assert first != second and "clear yes or no" in second


def test_llm_cannot_override_keyword_decline(monkeypatch):
    monkeypatch.setattr(approvals, "_llm_decision", lambda q, a, c: ("approve", ""))
    a = _new()
    assert approvals.interpret(a, "no", None)["decision"] == "decline"


def test_llm_used_only_when_unclear(monkeypatch):
    monkeypatch.setattr(approvals, "_llm_decision", lambda q, a, c: ("approve", ""))
    a = _new()
    assert approvals.interpret(a, "absolutely fine by me, go on then", None)["decision"] == "approve"


def test_resolved_approval_cannot_be_changed():
    a = _new()
    assert a.resolve("decline", "click")
    assert not a.resolve("approve", "click")
    assert a.status == "declined"
    assert approvals.interpret(a, "yes", None)["decision"] == "closed"


def test_expired_cannot_be_approved_and_wait_returns_decline():
    a = _new()
    a.expire_if_pending("osa-system stopped waiting for an answer.")
    assert a.wait() == "decline"
    assert not a.resolve("approve", "click")


def test_wait_blocks_until_answered():
    a = _new()
    out = []
    t = threading.Thread(target=lambda: out.append(a.wait()))
    t.start()
    t.join(0.2)
    assert t.is_alive()          # no Rigel-side timeout
    a.resolve("approve", "click")
    t.join(1)
    assert out == ["approve"]


def test_accept_content_fills_booleans_only():
    schema = {"properties": {"approve": {"type": "boolean"}, "note": {"type": "string", "default": "x"},
                             "other": {"type": "string"}}}
    assert approvals.accept_content(schema) == {"approve": True, "note": "x"}


def test_spoken_summary_names_action_target_and_risk():
    a = _new()
    assert "fs delete on /tmp/x.txt" in a.spoken and "irreversible" in a.spoken
    assert a.spoken.endswith("Should I go ahead?")


def test_pending_lists_only_open():
    a, b = _new(), _new()
    b.resolve("decline", "click")
    ids = {p["id"] for p in approvals.pending()}
    assert a.id in ids and b.id not in ids
    a.resolve("decline", "click")


# --- 2026-11-23 live bug: a grunt approved a file deletion -------------------
# The four listen-once transcripts from that run, plus the worst case: a model
# that says "approve" about any of them. None may approve.
@pytest.mark.parametrize("text", ["Mm-hmm", "mm", "uh huh", "Ugh", "Here we go. Ugh.", "Goodbye, wow.",
                                  "\u266a Scenes from a house \u266a Eh.", "Hmm...", "huh"])
def test_noise_never_approves_even_if_llm_says_approve(monkeypatch, text):
    monkeypatch.setattr(approvals, "_llm_decision", lambda q, a, c: ("approve", ""))
    a = _new()
    r = approvals.interpret(a, text, None)
    assert r["decision"] == "unclear" and a.status == "pending" and r["follow_up"]


@pytest.mark.parametrize("text", ["Here we go, the answer is probably yes",
                                  "yes, no wait", "yes I guess", "I think yes"])
def test_llm_approve_needs_a_clear_yes_at_the_start(monkeypatch, text):
    monkeypatch.setattr(approvals, "_llm_decision", lambda q, a, c: ("approve", ""))
    a = _new()
    assert approvals.interpret(a, text, None)["decision"] == "unclear"
    assert a.status == "pending"


def test_llm_still_approves_a_clear_long_yes(monkeypatch):
    # Long but unambiguous: the model may still approve, as before.
    monkeypatch.setattr(approvals, "_llm_decision", lambda q, a, c: ("approve", ""))
    a = _new()
    assert approvals.interpret(a, "absolutely fine by me, go on then", None)["decision"] == "approve"


def test_filler_never_reaches_the_llm(monkeypatch):
    calls = []
    monkeypatch.setattr(approvals, "_llm_decision", lambda q, a, c: calls.append(a) or ("approve", ""))
    a = _new()
    approvals.interpret(a, "Mm-hmm", None)
    assert calls == []
