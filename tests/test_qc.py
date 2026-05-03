"""Tests for publishing_core.qc."""
from unittest.mock import MagicMock, patch

import pytest

from publishing_core import qc
from publishing_core.qc import (
    QcGateError, QcResult,
    check_audio_present, check_captions_file, check_duration_sane,
    check_first_frame_brightness, run_all_checks,
)


# ── Real ffprobe/ffmpeg integration tests using the published San Diego video ──

import os
SAN_DIEGO = os.path.expanduser(
    "~/dev/uavhq/media/processed/san-diego-anomaly-final.mp4"
)
HAS_REAL_VIDEO = os.path.exists(SAN_DIEGO)


@pytest.mark.skipif(not HAS_REAL_VIDEO, reason="san-diego-anomaly-final.mp4 not present")
def test_real_video_duration_passes():
    r = check_duration_sane(SAN_DIEGO)
    assert r.passed, r.message
    assert 400 < r.details["duration"] < 600  # ~7:59 = 479s


@pytest.mark.skipif(not HAS_REAL_VIDEO, reason="san-diego-anomaly-final.mp4 not present")
def test_real_video_first_frame_passes():
    r = check_first_frame_brightness(SAN_DIEGO)
    # The veo intro is dark navy but well above pure-black threshold
    assert r.passed, r.message


@pytest.mark.skipif(not HAS_REAL_VIDEO, reason="san-diego-anomaly-final.mp4 not present")
def test_real_video_audio_passes():
    r = check_audio_present(SAN_DIEGO)
    assert r.passed, r.message
    assert r.details["peak_db"] > -10


@pytest.mark.skipif(not HAS_REAL_VIDEO, reason="san-diego-anomaly-final.mp4 not present")
def test_real_video_run_all_passes():
    r = run_all_checks(SAN_DIEGO)
    assert r.passed, r.message
    assert "PASS" in r.message


# ── Synthetic / mocked tests (always run) ──

def test_duration_too_short_fails(tmp_path, monkeypatch):
    def fake_probe(args, **kw):
        return {"format": {"duration": "2.5"}}
    monkeypatch.setattr(qc, "_run_ffprobe", fake_probe)
    fake_video = tmp_path / "tiny.mp4"
    fake_video.write_bytes(b"x")
    r = check_duration_sane(fake_video, min_seconds=5)
    assert not r.passed
    assert "below minimum" in r.message


def test_duration_too_long_fails(monkeypatch, tmp_path):
    def fake_probe(args, **kw):
        return {"format": {"duration": "99999"}}
    monkeypatch.setattr(qc, "_run_ffprobe", fake_probe)
    r = check_duration_sane(tmp_path / "x.mp4", max_seconds=7200)
    assert not r.passed
    assert "exceeds maximum" in r.message


def test_audio_check_no_stream_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(qc, "_run_ffprobe",
                        lambda args, **kw: {"streams": [{"codec_type": "video"}]})
    r = check_audio_present(tmp_path / "x.mp4")
    assert not r.passed
    assert "No audio stream" in r.message


def test_captions_missing_file_fails(tmp_path):
    r = check_captions_file(tmp_path / "nope.srt")
    assert not r.passed
    assert "not found" in r.message


def test_captions_too_short_fails(tmp_path):
    p = tmp_path / "tiny.srt"
    p.write_text("1\n00:00:00 --> 00:00:01\nhi\n")
    r = check_captions_file(p, min_lines=10)
    assert not r.passed
    assert "only" in r.message


def test_captions_valid_passes(tmp_path):
    p = tmp_path / "ok.srt"
    p.write_text("\n".join(f"line {i}" for i in range(20)))
    r = check_captions_file(p)
    assert r.passed
    assert r.details["lines"] == 20


def test_qc_gate_error_is_runtime_error():
    """Sanity: QcGateError can be raised + caught as RuntimeError."""
    with pytest.raises(RuntimeError, match="bad"):
        raise QcGateError("bad")
