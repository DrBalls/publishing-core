"""Shared auth chain for publishing pipelines.

Resolves credentials in this order (per provider):
  1. ``os.environ[KEY]`` if set
  2. ``~/.hermes/.env`` file
  3. (Anthropic only) ``~/.claude/.credentials.json`` Claude Max OAuth token

Raises ``RuntimeError`` with a clear remediation message if nothing works.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

CLAUDE_OAUTH_PATH = Path.home() / ".claude" / ".credentials.json"
HERMES_ENV = Path.home() / ".hermes" / ".env"


def _read_hermes_env_var(name: str) -> Optional[str]:
    """Read a key from process env, falling back to ~/.hermes/.env.

    Comment lines (starting with ``#``) and empty values are skipped.
    """
    if name in os.environ and os.environ[name]:
        return os.environ[name]
    if not HERMES_ENV.exists():
        return None
    try:
        for line in HERMES_ENV.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(f"{name}="):
                val = line.split("=", 1)[1].strip()
                # Strip surrounding quotes if present
                if val and val[0] in ('"', "'") and val[-1] == val[0]:
                    val = val[1:-1]
                return val or None
    except OSError:
        return None
    return None


def _load_claude_oauth() -> Optional[str]:
    """Return the Claude Max OAuth access token if present, else None."""
    if not CLAUDE_OAUTH_PATH.exists():
        return None
    try:
        creds = json.loads(CLAUDE_OAUTH_PATH.read_text())
        return creds.get("claudeAiOauth", {}).get("accessToken")
    except (OSError, json.JSONDecodeError):
        return None


def get_anthropic_client():
    """Return an Anthropic client. Tries API key first, then Claude Max OAuth.

    Raises:
        RuntimeError: if no credential source works.
    """
    import anthropic

    api_key = _read_hermes_env_var("ANTHROPIC_API_KEY")
    if api_key:
        return anthropic.Anthropic(api_key=api_key)

    oauth = _load_claude_oauth()
    if oauth:
        return anthropic.Anthropic(
            auth_token=oauth,
            default_headers={"anthropic-beta": "oauth-2025-04-20"},
        )

    raise RuntimeError(
        "No Anthropic credentials. Set ANTHROPIC_API_KEY in ~/.hermes/.env "
        "or run `claude login`."
    )


def get_gemini_key() -> str:
    """Return GEMINI_API_KEY or raise RuntimeError."""
    key = _read_hermes_env_var("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set in ~/.hermes/.env")
    return key


def get_elevenlabs_key() -> str:
    """Return ELEVENLABS_API_KEY or raise RuntimeError."""
    key = _read_hermes_env_var("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY not set in ~/.hermes/.env")
    return key


def get_anthropic_key_or_none() -> Optional[str]:
    """Return ANTHROPIC_API_KEY or None (for callers that need to choose a path)."""
    return _read_hermes_env_var("ANTHROPIC_API_KEY")
