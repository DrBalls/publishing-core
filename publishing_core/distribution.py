"""Cross-platform fan-out: turn a YouTube publish into LinkedIn + X + Bluesky posts.

Generates platform-specific copy via Claude, then dispatches to the relevant
skills/CLIs (linkedin, xurl, bluesky). The actual posting commands are
*returned*, not executed — this lets cron/CLI callers decide whether to
auto-post or hand off to the user for review.

Usage:
    from publishing_core.distribution import generate_fan_out_posts

    posts = generate_fan_out_posts(
        title="United Drone Strike at 3,000 Feet Over San Diego",
        video_id="oXOSpUP7bss",
        blog_url="https://uavhq.com/blog/united-airlines-drone-strike-...",
        summary="A United Airlines flight reported striking a drone at 3,000 ft on approach to KSAN — 2,600 ft above the legal Part 107 ceiling, inside Class B airspace.",
    )
    # → {"linkedin": "...", "x": "...", "bluesky": "..."}
"""
from __future__ import annotations

from typing import Optional

from publishing_core.auth import get_anthropic_client
from publishing_core.models import get_model

YOUTUBE_URL_FMT = "https://youtu.be/{video_id}"


PROMPT_TEMPLATE = """\
You are writing a social media post that points to a new YouTube video and its companion blog article.

VIDEO TITLE: {title}
VIDEO URL: {video_url}
BLOG URL: {blog_url}
SUMMARY (one paragraph from Wes's analysis): {summary}

CHANNEL CONTEXT: UAVHQ — drone industry intelligence. Wesley Alexander, senior test pilot + FAA drone regulations consultant. Authoritative, direct, operator-focused. NOT consumer / hobbyist.

TASK: Write THREE platform-tailored posts. Output exactly this format with the headers:

=== LINKEDIN ===
(2-4 short paragraphs. Open with a hook — a specific number, a counterintuitive observation, or a sharp question. Reference Wes's experience implicitly. End with the video link, then the blog link on a new line. No hashtags. ~600-1200 chars total.)

=== X ===
(One tweet under 270 chars. Hard hook — a number or contradiction. Include the video URL. Max one hashtag if any. NO platitudes.)

=== BLUESKY ===
(One post under 280 chars. Conversational tone, slightly more analytical than X. Include the video URL. NO hashtags.)

Write all three now. Use no emojis except an occasional ✈️ or 🛩 if it lands naturally.
"""


def _parse_response(text: str) -> dict[str, str]:
    """Split the model output into {linkedin, x, bluesky} dict."""
    parts: dict[str, str] = {}
    current_key: Optional[str] = None
    buffer: list[str] = []

    def flush():
        if current_key:
            parts[current_key] = "\n".join(buffer).strip()

    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "=== LINKEDIN ===":
            flush()
            current_key = "linkedin"
            buffer = []
        elif stripped == "=== X ===":
            flush()
            current_key = "x"
            buffer = []
        elif stripped == "=== BLUESKY ===":
            flush()
            current_key = "bluesky"
            buffer = []
        else:
            if current_key:
                buffer.append(line)
    flush()
    return parts


def generate_fan_out_posts(
    *,
    title: str,
    video_id: str,
    blog_url: str,
    summary: str,
    model: Optional[str] = None,
) -> dict[str, str]:
    """Generate platform-specific social posts for a new video publish.

    Returns dict with keys ``linkedin``, ``x``, ``bluesky``. Empty string for
    any platform that didn't parse cleanly.
    """
    client = get_anthropic_client()
    chosen_model = model or get_model("social_post_generation")
    prompt = PROMPT_TEMPLATE.format(
        title=title,
        video_url=YOUTUBE_URL_FMT.format(video_id=video_id),
        blog_url=blog_url,
        summary=summary,
    )
    msg = client.messages.create(
        model=chosen_model,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text if msg.content else ""
    posts = _parse_response(text)

    return {
        "linkedin": posts.get("linkedin", ""),
        "x": posts.get("x", ""),
        "bluesky": posts.get("bluesky", ""),
    }


def shell_commands_for_posts(posts: dict[str, str]) -> dict[str, str]:
    """Return ready-to-run shell commands for each platform.

    The actual posting tools (``linkedin`` skill, ``xurl``, ``bluesky`` skill)
    are CLI/skill-driven; this helper wraps the generated text into the right
    invocation. Caller decides whether to execute.
    """
    cmds: dict[str, str] = {}
    if posts.get("linkedin"):
        # LinkedIn skill posts via the user-attached account
        text = posts["linkedin"].replace('"', '\\"')
        cmds["linkedin"] = f'echo "Use linkedin skill to post:\\n\\n{text}"'
    if posts.get("x"):
        text = posts["x"].replace("'", "'\"'\"'")
        cmds["x"] = f"xurl tweet '{text}'"
    if posts.get("bluesky"):
        text = posts["bluesky"].replace("'", "'\"'\"'")
        cmds["bluesky"] = f"# Use bluesky skill to post: '{text}'"
    return cmds
