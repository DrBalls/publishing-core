"""Tests for publishing_core.auth."""
import pytest

from publishing_core import auth


def test_anthropic_client_creates_when_key_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake-not-real")
    c = auth.get_anthropic_client()
    assert c is not None


def test_gemini_key_raises_when_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(auth, "HERMES_ENV", tmp_path / "no.env")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        auth.get_gemini_key()


def test_elevenlabs_key_raises_when_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setattr(auth, "HERMES_ENV", tmp_path / "no.env")
    with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY"):
        auth.get_elevenlabs_key()


def test_read_hermes_env_var_prefers_environ(monkeypatch, tmp_path):
    monkeypatch.setenv("FOO_KEY", "from-environ")
    env = tmp_path / ".env"
    env.write_text("FOO_KEY=from-file\n")
    monkeypatch.setattr(auth, "HERMES_ENV", env)
    assert auth._read_hermes_env_var("FOO_KEY") == "from-environ"


def test_read_hermes_env_var_falls_back_to_file(monkeypatch, tmp_path):
    monkeypatch.delenv("BAR_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("# a comment\nBAR_KEY=from-file\nOTHER=ignored\n")
    monkeypatch.setattr(auth, "HERMES_ENV", env)
    assert auth._read_hermes_env_var("BAR_KEY") == "from-file"


def test_read_hermes_env_var_skips_commented_keys(monkeypatch, tmp_path):
    monkeypatch.delenv("BAZ_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("# BAZ_KEY=disabled-by-comment\n")
    monkeypatch.setattr(auth, "HERMES_ENV", env)
    assert auth._read_hermes_env_var("BAZ_KEY") is None


def test_read_hermes_env_var_strips_quotes(monkeypatch, tmp_path):
    monkeypatch.delenv("QUOTED_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text('QUOTED_KEY="value-in-quotes"\n')
    monkeypatch.setattr(auth, "HERMES_ENV", env)
    assert auth._read_hermes_env_var("QUOTED_KEY") == "value-in-quotes"


def test_load_claude_oauth_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "CLAUDE_OAUTH_PATH", tmp_path / "missing.json")
    assert auth._load_claude_oauth() is None


def test_load_claude_oauth_valid(monkeypatch, tmp_path):
    p = tmp_path / "creds.json"
    p.write_text('{"claudeAiOauth": {"accessToken": "sk-ant-oat01-FAKE"}}')
    monkeypatch.setattr(auth, "CLAUDE_OAUTH_PATH", p)
    assert auth._load_claude_oauth() == "sk-ant-oat01-FAKE"


def test_anthropic_client_falls_back_to_oauth(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(auth, "HERMES_ENV", tmp_path / "no.env")
    p = tmp_path / "creds.json"
    p.write_text('{"claudeAiOauth": {"accessToken": "sk-ant-oat01-OAUTH"}}')
    monkeypatch.setattr(auth, "CLAUDE_OAUTH_PATH", p)
    c = auth.get_anthropic_client()
    assert c is not None


def test_anthropic_client_raises_when_nothing(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(auth, "HERMES_ENV", tmp_path / "no.env")
    monkeypatch.setattr(auth, "CLAUDE_OAUTH_PATH", tmp_path / "no.json")
    with pytest.raises(RuntimeError, match="No Anthropic credentials"):
        auth.get_anthropic_client()
