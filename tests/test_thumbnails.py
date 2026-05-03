"""Tests for publishing_core.thumbnails."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from publishing_core import thumbnails


def test_missing_style_ref_raises(monkeypatch, tmp_path):
    fake_ref = tmp_path / "missing.png"
    monkeypatch.setattr(thumbnails, "STYLE_REF_DEFAULT", fake_ref)
    with pytest.raises(FileNotFoundError, match="Style reference"):
        thumbnails.generate_uavhq_thumbnail(
            topic="x", out_path=str(tmp_path / "out.png"),
        )


def test_missing_script_raises(monkeypatch, tmp_path):
    # Make style ref exist but script missing
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"fake")
    monkeypatch.setattr(thumbnails, "STYLE_REF_DEFAULT", ref)
    monkeypatch.setattr(thumbnails, "NANO_BANANA_SCRIPT", tmp_path / "no.py")
    with pytest.raises(FileNotFoundError, match="Nano Banana Pro"):
        thumbnails.generate_uavhq_thumbnail(
            topic="x", out_path=str(tmp_path / "out.png"),
        )


def test_format_longform_uses_16_9(monkeypatch, tmp_path):
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"fake")
    script = tmp_path / "gen.py"
    script.write_text("# stub")

    out = tmp_path / "out.png"
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        # Simulate script writing the file
        out.write_bytes(b"fake-png")
        return MagicMock(returncode=0, stdout="OK", stderr="")

    monkeypatch.setattr(thumbnails, "STYLE_REF_DEFAULT", ref)
    monkeypatch.setattr(thumbnails, "NANO_BANANA_SCRIPT", script)
    monkeypatch.setattr(thumbnails.subprocess, "run", fake_run)
    monkeypatch.setattr(thumbnails.shutil, "which", lambda x: f"/usr/bin/{x}")
    monkeypatch.setattr(thumbnails, "get_gemini_key", lambda: "fake-key")

    result = thumbnails.generate_uavhq_thumbnail(
        topic="test", out_path=str(out), format="longform",
    )
    assert result == out
    cmd_str = " ".join(captured["cmd"])
    assert "1280x720" in cmd_str or "16:9" in cmd_str


def test_format_short_uses_9_16(monkeypatch, tmp_path):
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"fake")
    script = tmp_path / "gen.py"
    script.write_text("# stub")

    out = tmp_path / "out.png"
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        out.write_bytes(b"fake-png")
        return MagicMock(returncode=0, stdout="OK", stderr="")

    monkeypatch.setattr(thumbnails, "STYLE_REF_DEFAULT", ref)
    monkeypatch.setattr(thumbnails, "NANO_BANANA_SCRIPT", script)
    monkeypatch.setattr(thumbnails.subprocess, "run", fake_run)
    monkeypatch.setattr(thumbnails.shutil, "which", lambda x: f"/usr/bin/{x}")
    monkeypatch.setattr(thumbnails, "get_gemini_key", lambda: "fake-key")

    thumbnails.generate_uavhq_thumbnail(
        topic="test", out_path=str(out), format="short",
    )
    cmd_str = " ".join(captured["cmd"])
    assert "1080x1920" in cmd_str or "9:16" in cmd_str


def test_subprocess_failure_propagates(monkeypatch, tmp_path):
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"fake")
    script = tmp_path / "gen.py"
    script.write_text("# stub")

    monkeypatch.setattr(thumbnails, "STYLE_REF_DEFAULT", ref)
    monkeypatch.setattr(thumbnails, "NANO_BANANA_SCRIPT", script)
    monkeypatch.setattr(thumbnails.shutil, "which", lambda x: f"/usr/bin/{x}")
    monkeypatch.setattr(thumbnails, "get_gemini_key", lambda: "fake-key")
    monkeypatch.setattr(thumbnails.subprocess, "run",
                        lambda *a, **k: MagicMock(returncode=1, stdout="", stderr="boom"))

    with pytest.raises(RuntimeError, match="exit 1"):
        thumbnails.generate_uavhq_thumbnail(
            topic="x", out_path=str(tmp_path / "out.png"),
        )


def test_to_youtube_jpg_calls_ffmpeg(monkeypatch, tmp_path):
    src = tmp_path / "src.png"
    src.write_bytes(b"fake-png")
    out = tmp_path / "out.jpg"

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        out.write_bytes(b"fake-jpg")
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(thumbnails.subprocess, "run", fake_run)
    monkeypatch.setattr(thumbnails.shutil, "which", lambda x: f"/usr/bin/{x}")

    result = thumbnails.to_youtube_thumbnail_jpg(src, out)
    assert result == out
    assert "ffmpeg" in captured["cmd"][0]
    assert "scale=1280:720" in " ".join(captured["cmd"])
