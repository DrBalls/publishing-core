"""Unified thumbnail generation for UAVHQ video content.

Single API path for both long-form and Shorts thumbnails: Nano Banana Pro
with a locked style reference image, ensuring brand consistency across
all video formats.

Replaces the previous split where:
  - Long-form: ad-hoc Nano Banana Pro prompts (varying styles)
  - Shorts:    Gemini Imagen base + Pillow text overlay (different aesthetic)

Style reference: ``~/dev/uavhq-branding/thumbnail-style-reference.png`` —
the dark navy / cyan / amber aerospace look established in March 2026.

Usage:
    from publishing_core.thumbnails import generate_uavhq_thumbnail

    thumb_path = generate_uavhq_thumbnail(
        topic="United Airlines drone strike at 3000 ft over San Diego",
        out_path="/tmp/sd-thumb.png",
        format="longform",  # or "short" for 9:16 vertical
        headline="DRONE STRIKE",
        subhead="3,000 FT OVER SAN DIEGO",
    )
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Literal

from publishing_core.auth import get_gemini_key

STYLE_REF_DEFAULT = Path.home() / "dev" / "uavhq-branding" / "thumbnail-style-reference.png"
NANO_BANANA_SCRIPT = Path.home() / ".hermes" / "skills" / "openclaw-imports" / "nano-banana-pro" / "scripts" / "generate_image.py"

UAVHQ_BASE_PROMPT = """\
Cinematic professional YouTube thumbnail, {aspect_label}, UAVHQ branding style.

VISUAL STYLE (must match the input style reference image):
- Dark navy and deep teal background with subtle radar grid texture
- Dramatic cyan and amber accent lighting
- Professional aerospace / news-broadcast aesthetic — NOT consumer / hobbyist
- Moody atmospheric lighting with high contrast
- Sharp focus, photorealistic, cinematic depth of field

SUBJECT: {topic}

TEXT OVERLAY:
- Primary headline: "{headline}" — bold uppercase Barlow Condensed in white, upper-left or center
- Secondary line: "{subhead}" — cyan accent color, beneath headline
- Bottom-right corner: small UAVHQ wordmark

AVOID:
- Blurry text, generic stock-photo look, cluttered backgrounds
- Bright daytime palette, cartoon/illustrated style, hobbyist aesthetic
- Multiple small drone images (one is enough), confusing collages
"""


def generate_uavhq_thumbnail(
    *,
    topic: str,
    out_path: str | Path,
    format: Literal["longform", "short"] = "longform",
    headline: str = "",
    subhead: str = "",
    style_reference: Path | None = None,
    resolution: Literal["1K", "2K", "4K"] = "2K",
) -> Path:
    """Generate a UAVHQ-branded thumbnail via Nano Banana Pro.

    Returns the absolute path of the saved PNG.

    Args:
        topic: Free-form description of what the thumbnail depicts.
        out_path: Where to write the final PNG.
        format: "longform" (16:9) or "short" (9:16 vertical).
        headline: Primary text overlay (UPPERCASE, 1-3 words ideal).
        subhead: Secondary text overlay below headline.
        style_reference: Path to the style-lock image. Defaults to
            ``thumbnail-style-reference.png`` in uavhq-branding.
        resolution: Nano Banana Pro resolution tier.

    Raises:
        FileNotFoundError: if the style reference doesn't exist or the
            ``generate_image.py`` script is missing.
        RuntimeError: if generation fails or GEMINI_API_KEY is unset.
    """
    style_ref = Path(style_reference) if style_reference else STYLE_REF_DEFAULT
    if not style_ref.exists():
        raise FileNotFoundError(
            f"Style reference not found: {style_ref}. "
            f"Run setup_thumbnail_style_reference() or copy a canonical thumb to that path."
        )
    if not NANO_BANANA_SCRIPT.exists():
        raise FileNotFoundError(
            f"Nano Banana Pro script not found at {NANO_BANANA_SCRIPT}. "
            f"Install the openclaw-imports/nano-banana-pro skill."
        )

    # Validate API key (raises if missing)
    gemini_key = get_gemini_key()

    aspect_label = "16:9 widescreen 1280x720" if format == "longform" else "9:16 vertical 1080x1920"
    prompt = UAVHQ_BASE_PROMPT.format(
        aspect_label=aspect_label,
        topic=topic,
        headline=headline or "UAVHQ",
        subhead=subhead or "Tactical Brief",
    )

    out = Path(out_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    # Use uv run to invoke the script with the correct dependency env
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv not on PATH; install via `brew install uv`")

    cmd = [
        uv, "run", str(NANO_BANANA_SCRIPT),
        "--prompt", prompt,
        "--filename", str(out),
        "--input-image", str(style_ref),
        "--resolution", resolution,
    ]
    env = {**os.environ, "GEMINI_API_KEY": gemini_key}

    proc = subprocess.run(
        cmd, capture_output=True, text=True, env=env, timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Thumbnail generation failed (exit {proc.returncode}):\n"
            f"stdout: {proc.stdout[-500:]}\n"
            f"stderr: {proc.stderr[-500:]}"
        )

    if not out.exists():
        raise RuntimeError(f"Generation completed but output missing: {out}")

    return out


def to_youtube_thumbnail_jpg(
    src: str | Path,
    out: str | Path,
    *,
    width: int = 1280,
    height: int = 720,
    quality: int = 3,
) -> Path:
    """Convert a generated PNG to YouTube-ready 1280x720 JPG via ffmpeg.

    YouTube enforces <2MB and prefers 1280x720 for thumbnails. This helper
    standardizes the conversion step that was previously hand-coded after
    every thumbnail run.
    """
    src_path = Path(src).expanduser().resolve()
    out_path = Path(out).expanduser().resolve()

    if not src_path.exists():
        raise FileNotFoundError(src_path)

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg not on PATH")

    cmd = [
        ffmpeg, "-y", "-i", str(src_path),
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
               f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "-q:v", str(quality),
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg conversion failed (exit {proc.returncode}): {proc.stderr[-500:]}"
        )
    return out_path
