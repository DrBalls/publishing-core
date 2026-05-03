"""Tests for publishing_core.models."""
import pytest

from publishing_core import models
from publishing_core.models import get_default, get_model


def setup_function():
    models.reload()


def test_get_model_for_known_task():
    assert get_model("shorts_script_generation").startswith("claude-")


def test_get_model_unknown_raises():
    with pytest.raises(KeyError, match="Unknown model task"):
        get_model("nonexistent-task")


def test_get_default_claude_standard():
    assert get_default("claude", "standard").startswith("claude-")


def test_get_default_gemini_image():
    assert get_default("gemini", "image").startswith("gemini-")


def test_get_default_unknown_provider_raises():
    with pytest.raises(KeyError):
        get_default("nonexistent-provider", "standard")
