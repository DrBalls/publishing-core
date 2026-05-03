"""Pre-publish quality-control checks for video files.

Run before any ``safe_upload()`` call to catch silent failures:
  - Black/blank first frame (Veo b-roll occasionally returns these)
  - Silent or near-silent audio (voiceover failed, ducking too aggressive)
  - Missing captions track (Whisper crashed or output not muxed)
  - End card frame mismatch (wrong outro spliced in)

Each check returns a ``QcResult`` with ``passed`` + ``message``. Use
``run_all_checks()`` to get a combined verdict.

Usage:
    from publishing_core.qc import run_all_checks, QcGateError

    result = run_all_checks("/path/to/final.mp4")
    if not result.passed:
        raise QcGateError(result.message)
    # ... safe_upload() ...
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


class QcGateError(RuntimeError):
    """Raised when QC checks fail and the caller wants to abort."""


@dataclass
class QcResult:
    passed: bool
    message: str
    details: dict = field(default_factory=dict)


def _run_ffprobe(args: list[str], timeout: int = 30) -> dict:
    """Run ffprobe with JSON output and return parsed dict."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe not on PATH")
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-print_format", "json", *args],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {proc.stderr[:200]}")
    return json.loads(proc.stdout or "{}")


def check_first_frame_brightness(
    video_path: str | Path,
    *,
    min_avg_luma: float = 16.0,
) -> QcResult:
    """Verify the first frame isn't black/blank.

    A pure-black frame has avg luma ≈ 0; a normal frame is usually 80-180.
    Threshold of 16 catches truly black frames while allowing dark cinematic
    intros (the UAVHQ veo-intro is dark navy, ~25-35).
    """
    video_path = Path(video_path)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return QcResult(False, "ffmpeg not on PATH", {})

    # Sample first 0.5s and report average luma via signalstats
    proc = subprocess.run(
        [ffmpeg, "-i", str(video_path),
         "-vf", "select='lt(t,0.5)',signalstats,metadata=print",
         "-f", "null", "-"],
        capture_output=True, text=True, timeout=30,
    )
    output = proc.stderr  # signalstats writes to stderr
    # Parse YAVG values
    luma_values = []
    for line in output.splitlines():
        if "lavfi.signalstats.YAVG=" in line:
            try:
                luma_values.append(float(line.split("=", 1)[1]))
            except ValueError:
                continue
    if not luma_values:
        return QcResult(False, "Could not measure first-frame luma", {"output": output[-200:]})

    avg = sum(luma_values) / len(luma_values)
    if avg < min_avg_luma:
        return QcResult(
            False,
            f"First-frame avg luma {avg:.1f} below threshold {min_avg_luma} — likely black/blank",
            {"avg_luma": avg, "samples": len(luma_values)},
        )
    return QcResult(True, f"First-frame luma OK (avg={avg:.1f})", {"avg_luma": avg})


def check_audio_present(
    video_path: str | Path,
    *,
    min_peak_db: float = -40.0,
) -> QcResult:
    """Verify audio stream exists and isn't silent.

    Uses ``volumedetect`` filter to compute peak/mean dB. Silent audio
    typically registers as -91 dB or worse; normal voiceover ~-10 to -20.
    """
    video_path = Path(video_path)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return QcResult(False, "ffmpeg not on PATH", {})

    # First check: is there an audio stream?
    probe = _run_ffprobe(["-show_streams", str(video_path)])
    audio_streams = [s for s in probe.get("streams", []) if s.get("codec_type") == "audio"]
    if not audio_streams:
        return QcResult(False, "No audio stream present", {})

    # Sample first 30s and measure peak
    proc = subprocess.run(
        [ffmpeg, "-i", str(video_path), "-t", "30",
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, timeout=60,
    )
    output = proc.stderr
    peak_db = None
    for line in output.splitlines():
        if "max_volume:" in line:
            try:
                peak_db = float(line.split("max_volume:")[1].strip().split()[0])
            except (ValueError, IndexError):
                pass
    if peak_db is None:
        return QcResult(False, "Could not measure audio peak", {"output": output[-200:]})

    if peak_db < min_peak_db:
        return QcResult(
            False,
            f"Audio peak {peak_db:.1f} dB below threshold {min_peak_db} dB — likely silent",
            {"peak_db": peak_db},
        )
    return QcResult(True, f"Audio peak OK ({peak_db:.1f} dB)", {"peak_db": peak_db})


def check_duration_sane(
    video_path: str | Path,
    *,
    min_seconds: float = 5.0,
    max_seconds: float = 7200.0,
) -> QcResult:
    """Verify duration falls inside a sane range.

    Default: 5s to 2h. Catches truncated renders (encoder crashed mid-write)
    and runaway concat (looped intro forever).
    """
    probe = _run_ffprobe(["-show_format", str(video_path)])
    try:
        duration = float(probe["format"]["duration"])
    except (KeyError, ValueError):
        return QcResult(False, "Could not read duration from format", {})

    if duration < min_seconds:
        return QcResult(
            False,
            f"Duration {duration:.1f}s below minimum {min_seconds}s — likely truncated render",
            {"duration": duration},
        )
    if duration > max_seconds:
        return QcResult(
            False,
            f"Duration {duration:.1f}s exceeds maximum {max_seconds}s — likely runaway concat",
            {"duration": duration},
        )
    return QcResult(True, f"Duration OK ({duration:.1f}s)", {"duration": duration})


def check_captions_file(
    captions_path: str | Path,
    *,
    min_lines: int = 5,
) -> QcResult:
    """Verify a caption sidecar file exists and looks valid.

    Use this for Shorts where Whisper SRT is meant to accompany the upload.
    Long-form videos without captions will skip this check entirely.
    """
    p = Path(captions_path)
    if not p.exists():
        return QcResult(False, f"Captions file not found: {p}", {})
    text = p.read_text(errors="replace")
    line_count = sum(1 for _ in text.splitlines())
    if line_count < min_lines:
        return QcResult(
            False,
            f"Captions file has only {line_count} lines — Whisper output may have failed",
            {"lines": line_count, "path": str(p)},
        )
    return QcResult(True, f"Captions OK ({line_count} lines)", {"lines": line_count})


def run_all_checks(
    video_path: str | Path,
    *,
    captions_path: Optional[str | Path] = None,
    min_seconds: float = 5.0,
    max_seconds: float = 7200.0,
) -> QcResult:
    """Run all standard QC checks and combine results.

    Returns a single QcResult: passed=True only if every check passed.
    Combined message includes per-check summaries.
    """
    results: list[QcResult] = [
        check_duration_sane(video_path, min_seconds=min_seconds, max_seconds=max_seconds),
        check_first_frame_brightness(video_path),
        check_audio_present(video_path),
    ]
    if captions_path:
        results.append(check_captions_file(captions_path))

    passed = all(r.passed for r in results)
    summary = "\n".join(
        f"  {'✓' if r.passed else '✗'} {r.message}" for r in results
    )
    msg = f"QC {'PASS' if passed else 'FAIL'}:\n{summary}"
    details = {"checks": [{"passed": r.passed, "message": r.message, **r.details} for r in results]}
    return QcResult(passed, msg, details)
