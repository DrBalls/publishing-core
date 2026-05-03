"""Central model registry. Use get_model('shorts_script_generation') everywhere.

Single source of truth for model names. When models deprecate, edit
``models.yaml`` here — every consumer pipeline picks up the change automatically.
"""
from __future__ import annotations

from pathlib import Path

import yaml

_MODELS_PATH = Path(__file__).parent / "models.yaml"
_cache: dict | None = None


def _load() -> dict:
    """Load and cache the YAML registry. Tests can call ``reload()`` to reset."""
    global _cache
    if _cache is None:
        _cache = yaml.safe_load(_MODELS_PATH.read_text())
    return _cache


def reload() -> None:
    """Force a reload of the YAML on next access (useful in tests)."""
    global _cache
    _cache = None


def get_model(task: str) -> str:
    """Return the model name registered for a named task.

    Raises:
        KeyError: if the task is not in models.yaml under ``tasks:``.

    Example:
        >>> get_model("shorts_script_generation")
        'claude-sonnet-4-5'
    """
    cfg = _load()
    tasks = cfg.get("tasks", {})
    if task not in tasks:
        raise KeyError(
            f"Unknown model task: {task!r}. "
            f"Add it to {_MODELS_PATH} under 'tasks:'."
        )
    return tasks[task]


def get_default(provider: str, tier: str = "standard") -> str:
    """Return the default model for a provider+tier.

    Args:
        provider: One of ``claude``, ``gemini``, ``elevenlabs``, ``whisper``.
        tier: Provider-specific tier name (``fast``, ``standard``, ``deep``,
            ``image``, ``text``, etc.).

    Raises:
        KeyError: if the provider/tier combination is not in models.yaml.
    """
    cfg = _load()
    return cfg["defaults"][provider][tier]
