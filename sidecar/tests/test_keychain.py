"""Keychain key lookup: Keychain first, env fallback, never leaks the key."""
import subprocess

import pytest

from sidecar import keychain, llm_providers


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    keychain.forget()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(keychain.sys, "platform", "darwin")
    monkeypatch.setattr(keychain.os.path, "exists", lambda p: True)
    yield
    keychain.forget()


def _fake_security(monkeypatch, value, rc=0):
    calls = []

    def run(argv, **kw):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, rc, stdout=value + "\n", stderr="")
    monkeypatch.setattr(keychain.subprocess, "run", run)
    return calls


def test_reads_keychain_and_caches(monkeypatch):
    calls = _fake_security(monkeypatch, "sk-ant-api-test")
    assert keychain.anthropic_key() == "sk-ant-api-test"
    assert keychain.anthropic_key() == "sk-ant-api-test"
    assert len(calls) == 1
    assert calls[0] == ["/usr/bin/security", "find-generic-password", "-s", "rigel-anthropic-key", "-w"]
    assert keychain.anthropic_key_source() == "keychain"


def test_falls_back_to_env(monkeypatch):
    _fake_security(monkeypatch, "", rc=44)  # item not found
    assert keychain.anthropic_key() is None
    assert keychain.anthropic_key_source() is None
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert keychain.anthropic_key_source() == "env"


def test_client_gets_the_keychain_key(monkeypatch):
    _fake_security(monkeypatch, "sk-ant-api-test")
    seen = {}

    class FakeAnthropic:
        def __init__(self, **kw):
            seen.update(kw)
    monkeypatch.setattr(llm_providers.anthropic, "Anthropic", FakeAnthropic)
    llm_providers.anthropic_client()
    assert seen == {"api_key": "sk-ant-api-test"}


def test_source_never_contains_the_key(monkeypatch):
    _fake_security(monkeypatch, "sk-ant-api-secret")
    assert "sk-ant" not in str(llm_providers.claude_api_key_source())
