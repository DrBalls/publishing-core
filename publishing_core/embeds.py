"""HTML embed snippets for blog video integration.

These produce the canonical UAVHQ blog video embed (matches the lazy-load
``srcdoc`` pattern used in posts like ``amazon-drone-crashes-...``). Use the
``embed_video.py`` CLI in ``~/dev/uavhq/scripts/`` to apply them to a post.
"""
from __future__ import annotations

from textwrap import dedent


def youtube_embed(
    video_id: str,
    title: str,
    more_videos_url: str = "/videos",
) -> str:
    """Return the canonical UAVHQ blog video embed block.

    Uses a lazy-loaded ``<iframe>`` with ``srcdoc`` so the YouTube player only
    loads on click — keeps Lighthouse scores high and avoids autoloading 3rd-
    party JS for every page view.

    Args:
        video_id: YouTube video ID (the part after ``v=`` or ``youtu.be/``).
        title: Human-readable title for the caption + accessibility attributes.
        more_videos_url: Where the "More videos →" link points.

    Returns:
        HTML block ready to insert into a UAVHQ blog post body.
    """
    title_attr = title.replace('"', "&quot;").replace("'", "&#39;")
    return dedent(f"""\
        <!-- Embedded Video -->
        <div style="background: var(--card-bg); border: 1px solid var(--border-subtle); border-radius: 12px; overflow: hidden; margin-bottom: 2.5rem;">
          <div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; background: #000;">
            <iframe
              style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0;"
              src="about:blank"
              srcdoc="<style>*{{padding:0;margin:0;overflow:hidden}}html,body{{height:100%}}img,span{{position:absolute;width:100%;top:0;bottom:0;margin:auto}}span{{height:1.5em;text-align:center;font:48px/1.5 sans-serif;color:white;text-shadow:0 0 0.5em black}}</style><a href='https://www.youtube.com/embed/{video_id}?autoplay=1'><img src='https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg' alt='{title_attr}'><span>&#x25BA;</span></a>"
              loading="lazy"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowfullscreen
              title="{title_attr}"
            ></iframe>
          </div>
          <div style="padding: 1rem 1.5rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
            <span style="color: var(--text-secondary); font-size: 0.9rem;">Watch: {title}</span>
            <a href="{more_videos_url}" style="color: var(--accent-blue); text-decoration: none; font-weight: 600; font-size: 0.85rem;">More videos &rarr;</a>
          </div>
        </div>
        """)
