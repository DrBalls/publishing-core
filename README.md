# publishing-core

[![tests](https://github.com/DrBalls/publishing-core/actions/workflows/tests.yml/badge.svg)](https://github.com/DrBalls/publishing-core/actions/workflows/tests.yml)

Shared Python primitives for the UAVHQ + Digital Splendor publishing pipelines.

## What's in here

| Module | Purpose |
|---|---|
| `auth` | Anthropic / Gemini / ElevenLabs credential chain (env → `~/.hermes/.env` → Claude Max OAuth fallback) |
| `models` | Single source of truth for model names per task — `get_model("shorts_script_generation")` |
| `embeds` | HTML embed snippets — `youtube_embed(video_id, title)` |
| `costs` | SQLite cost ledger — auto-tracks spend per project + per run |
| `tracked_clients` | `TrackedAnthropic` wrapper that auto-logs every API call |
| `state` | Generic resume-on-failure state machine for multi-stage pipelines |
| `distribution` | Cross-platform fan-out — generates LinkedIn + X + Bluesky copy |
| `thumbnails` | Unified UAVHQ thumbnail gen (Nano Banana Pro + locked style ref) |
| `retry` | Exponential-backoff retry decorator |
| `qc` | Pre-publish quality-control checks (frame brightness, audio peak, duration, captions) |

## Install (editable, into a consumer venv)

```bash
cd ~/dev/<consumer-project>
uv pip install -e ~/dev/_publishing-core
```

## Run tests

```bash
cd ~/dev/_publishing-core
uv venv --python 3.12
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -v
```

CI runs on Python 3.12 + 3.13 via GitHub Actions on every push.

## Quickstart examples

### Generate + log a Claude call

```python
from publishing_core.tracked_clients import TrackedAnthropic
from publishing_core.models import get_model

client = TrackedAnthropic(project="uavhq", run_id="san-diego-anomaly")
msg = client.messages.create(
    model=get_model("shorts_script_generation"),
    max_tokens=1500,
    messages=[{"role": "user", "content": "..."}],
)
# Cost auto-logged to ~/.hermes/cost-ledger.db
```

### Insert a YouTube embed into a blog post

```python
from publishing_core.embeds import youtube_embed

html = youtube_embed("oXOSpUP7bss", "United Drone Strike at 3,000 Feet…")
# → ready-to-paste lazy-load iframe block
```

### Resume a multi-stage pipeline after crash

```python
from publishing_core.state import PipelineState

state = PipelineState.load(
    "/tmp/run-state.json",
    stages=["normalize", "mix", "encode_intro", "encode_outro", "concat", "upload"],
)
for stage in state.stages:
    if state.is_done(stage):
        continue
    # … do the work …
    state.complete_stage(stage, artifacts={"path": "/tmp/x.mp4"})
    state.save()
```

### Generate cross-platform social posts

```python
from publishing_core.distribution import generate_fan_out_posts

posts = generate_fan_out_posts(
    title="United Drone Strike at 3,000 Feet Over San Diego",
    video_id="oXOSpUP7bss",
    blog_url="https://uavhq.com/blog/united-airlines-drone-strike-...",
    summary="A United Airlines flight reported striking a drone at 3,000 ft on approach to KSAN…",
)
# → {"linkedin": "...", "x": "...", "bluesky": "..."}
```

### Pre-publish QC gate

```python
from publishing_core.qc import run_all_checks, QcGateError

result = run_all_checks("/path/to/final.mp4", captions_path="/path/to/captions.srt")
if not result.passed:
    raise QcGateError(result.message)
# … safe_upload(...)
```

## Versioning

Semver. Bump on any breaking API change. Consumers pin via `publishing-core==X.Y` or use `uv.lock`.

## Roadmap (Phase 5+)

Not yet released — these will land as need arises:
- Hoist YouTube upload helpers from `uavhq-branding/scripts/uavhq_youtube.py`
- Hoist Whisper caption + ducking helpers from `youtube-shorts-pipeline`
- Add Discord / Yuanbao fan-out targets (currently just LinkedIn / X / Bluesky)

---

*Created 2026-05-02 as part of [Content Publishing Modernization Plan v1.0](https://github.com/DrBalls/publishing-core).*
