"""Rigel's secrets, read from the macOS login Keychain.

The Anthropic API key lives in the Keychain as a generic password:
service ``rigel-anthropic-key`` (override with ``RIGEL_KEYCHAIN_SERVICE``),
stored there 2026-11-15 from Tony's shared Codehome key. Rigel reads it
with ``/usr/bin/security`` when a Claude call needs it and hands it straight
to the Anthropic client: never into an environment variable, a file, a
log line, an API response or the UI. Only *whether* a key was found, and
from where, is ever reported.

Order: Keychain first, then ``ANTHROPIC_API_KEY`` / ``ANTHROPIC_AUTH_TOKEN``
in the environment (the SDK's own lookup), so an explicit env var still
works off-Mac or for a one-off override.

To (re)store the key without it appearing on screen or in ``ps``:
    k=$(pbpaste); printf 'add-generic-password -U -s rigel-anthropic-key -a "$USER" -w "%s"\\n' "$k" | security -i; unset k
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading

KEYCHAIN_SERVICE = os.getenv("RIGEL_KEYCHAIN_SERVICE", "rigel-anthropic-key")
SECURITY = "/usr/bin/security"

_LOCK = threading.Lock()
_CACHE: dict[str, str | None] = {}


def _from_keychain(service: str) -> str | None:
    if sys.platform != "darwin" or not os.path.exists(SECURITY):
        return None
    try:
        out = subprocess.run(
            [SECURITY, "find-generic-password", "-s", service, "-w"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = out.stdout.strip() if out.returncode == 0 else ""
    return value or None


def anthropic_key() -> str | None:
    """The Anthropic API key from the Keychain, or None (then the SDK falls
    back to the environment). Cached after the first successful read."""
    with _LOCK:
        if _CACHE.get(KEYCHAIN_SERVICE):
            return _CACHE[KEYCHAIN_SERVICE]
        value = _from_keychain(KEYCHAIN_SERVICE)
        if value:
            _CACHE[KEYCHAIN_SERVICE] = value
        return value


def anthropic_key_source() -> str | None:
    """'keychain', 'env' or None. Never the key itself."""
    if anthropic_key():
        return "keychain"
    if os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"):
        return "env"
    return None


def forget() -> None:
    """Drop the cached key (e.g. after it's rotated in the Keychain)."""
    with _LOCK:
        _CACHE.clear()
