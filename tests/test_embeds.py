"""Tests for publishing_core.embeds."""
from publishing_core.embeds import youtube_embed


def test_embed_contains_video_id():
    out = youtube_embed("abc123", "Test Title")
    assert "abc123" in out
    assert "Test Title" in out


def test_embed_uses_canonical_marker():
    """Used by embed_video.py CLI to detect already-embedded posts."""
    out = youtube_embed("abc", "T")
    assert "<!-- Embedded Video -->" in out


def test_embed_escapes_quotes_in_title():
    out = youtube_embed("xyz", 'A "quoted" title')
    # Quotes in HTML attributes (alt, title) must be escaped
    assert 'alt=\'A "quoted" title\'' not in out  # not in srcdoc raw
    assert "&quot;" in out  # escaped form is present


def test_embed_escapes_apostrophes():
    out = youtube_embed("xyz", "Wes's analysis")
    assert "&#39;" in out


def test_embed_links_to_more_videos():
    out = youtube_embed("xyz", "T", more_videos_url="/custom-videos")
    assert "/custom-videos" in out


def test_embed_uses_thumbnail_image():
    out = youtube_embed("VIDEO123", "T")
    assert "i.ytimg.com/vi/VIDEO123/maxresdefault.jpg" in out


def test_embed_uses_lazy_loading():
    out = youtube_embed("xyz", "T")
    assert 'loading="lazy"' in out
