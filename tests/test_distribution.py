"""Tests for publishing_core.distribution."""
from unittest.mock import MagicMock

import pytest

from publishing_core import distribution


def test_parse_response_well_formed():
    text = """=== LINKEDIN ===
This is the LinkedIn post.
Multiple lines ok.

=== X ===
Short tweet here.

=== BLUESKY ===
A bluesky post."""
    out = distribution._parse_response(text)
    assert "LinkedIn post" in out["linkedin"]
    assert "Short tweet" in out["x"]
    assert "bluesky post" in out["bluesky"]


def test_parse_response_missing_section():
    text = """=== LINKEDIN ===
Only one section."""
    out = distribution._parse_response(text)
    assert "Only one section" in out["linkedin"]
    assert "x" not in out
    assert "bluesky" not in out


def test_parse_response_handles_no_headers():
    out = distribution._parse_response("just plain text")
    assert out == {}


def test_generate_fan_out_uses_model_registry(monkeypatch):
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text="""=== LINKEDIN ===
Test post.
=== X ===
Tweet.
=== BLUESKY ===
Sky.""")]

    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response
    monkeypatch.setattr(distribution, "get_anthropic_client", lambda: fake_client)

    out = distribution.generate_fan_out_posts(
        title="Test", video_id="abc", blog_url="https://x.com/y",
        summary="Some analysis.",
    )
    assert out["linkedin"] == "Test post."
    assert out["x"] == "Tweet."
    assert out["bluesky"] == "Sky."

    # Verify it called the API with a real model name
    call_kwargs = fake_client.messages.create.call_args.kwargs
    assert call_kwargs["model"].startswith("claude-")


def test_shell_commands_for_x():
    posts = {"x": "Hello world", "linkedin": "", "bluesky": ""}
    cmds = distribution.shell_commands_for_posts(posts)
    assert "xurl tweet" in cmds["x"]
    assert "Hello world" in cmds["x"]


def test_shell_commands_skips_empty():
    posts = {"x": "", "linkedin": "", "bluesky": ""}
    cmds = distribution.shell_commands_for_posts(posts)
    assert cmds == {}
