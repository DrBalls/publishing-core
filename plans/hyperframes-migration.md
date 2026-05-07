# HyperFrames Migration Plan — UAVHQ Shorts Render Layer

**Status:** Phases 0–3 complete (2026-05-04). Phase 4 (cleanup) deferred.
**Created:** 2026-05-03
**Updated:** 2026-05-04 — HyperFrames render layer is now the canonical Shorts render path. Daily Short cron passes `--render-engine=hyperframes` explicitly; codebase default remains `legacy` as a rollback hatch.
**Author:** JARVIS (with Wes)
**Trigger:** Path B (Veo + Ken Burns concat) failed in production with resolution/framerate/duration drift. Architectural mismatch between fixed-8s Veo clips and variable-length Ken Burns segments cannot be cleanly resolved in ffmpeg concat. Time to replace the render layer with a declarative, single-pass renderer.

---

## TL;DR

Replace `pipeline/assemble.py` (per-segment ffmpeg + concat) with a **HyperFrames composition + render** step. Keep everything else (topic discovery, scripting, image gen, TTS, captions, upload).

- **Repo:** https://github.com/heygen-com/hyperframes
- **License:** Apache 2.0 (fully OSS, no per-render fees, no seat caps)
- **Stack:** Node.js ≥22 + FFmpeg + headless Chrome (Puppeteer)
- **Output:** deterministic single-pass MP4 at exact target resolution/framerate

---

## Why This Is the Right Move

### The class of bugs HyperFrames eliminates

The exact failure modes we hit on 2026-05-03:
1. Resolution mismatch between segment renderers (Veo 720p vs Ken Burns 1080p) → concat downscaled
2. Framerate mismatch (24fps vs 30fps) → concat normalized to lowest
3. Duration drift (Veo fixed 8s vs voiceover-driven 23s) → ~30s of missing video
4. Caption alignment fragile across segment boundaries

All of these are *concat-architecture problems*. HyperFrames doesn't concat — it renders one HTML composition deterministically frame-by-frame. The composition declares total duration, target resolution, target fps. Mismatch is impossible by design.

### Other wins

- **Captions become HTML/CSS** — no more ffmpeg drawtext or .ass file gymnastics. Style with Tailwind.
- **Ken Burns is one CSS transform + GSAP timeline** — not an ffmpeg zoompan filter chain.
- **Lower thirds, end cards, transitions** — all native HTML, agent-authorable.
- **Agent-first design** — explicitly built for AI to author. There's a Claude Code skill (`/hyperframes`) we can install.
- **Deterministic** — same input = identical output. Built for automated pipelines.
- **Catalog of 50+ pre-built blocks** — social overlays, transitions, data viz.

### What it does NOT replace

Stays the same:
- Topic discovery + dedup (`pipeline/topics.py`)
- Script writing via Gemini (`pipeline/draft.py`)
- B-roll image gen via Imagen/Nano Banana (`pipeline/broll.py`)
- TTS voiceover (`pipeline/voiceover.py`)
- Caption *timing* extraction (Whisper) — but rendering moves to HTML
- Thumbnail generation
- YouTube upload (`pipeline/upload.py`)
- State machine, dedup, draft cache

---

## Architecture: Before vs After

### Before (current)
```
draft.json
  ↓
broll.py     → broll_0.png, broll_1.png, broll_2.png
voiceover.py → voiceover_en.mp3
captions.py  → captions_en.srt + captions_en.ass
assemble.py  → anim_0.mp4 (Ken Burns) + anim_1.mp4 + anim_2.mp4
              → ffmpeg concat → merged_video.mp4
              → ffmpeg burn captions → final.mp4
end_card.py  → end_card.mp4
              → ffmpeg concat final + end_card → video.mp4
```

Failure surface: every ffmpeg call + every concat boundary.

### After (HyperFrames)
```
draft.json
  ↓
broll.py     → broll_0.png, broll_1.png, broll_2.png
voiceover.py → voiceover_en.mp3
captions.py  → captions.json (timing only)
compose.py   → composition.html (NEW — generates HyperFrames HTML from draft)
              → npx hyperframes render composition.html → video.mp4
```

Single render. Single resolution. Single fps. No concat. No drift.

---

## Migration Phases

### Phase 0 — Spike (1 day)
**Goal:** Prove HyperFrames can produce a UAVHQ Short matching current quality.

- [ ] Install Node 22 (already have FFmpeg)
- [ ] `npx hyperframes init uavhq-shorts-test`
- [ ] `npx skills add heygen-com/hyperframes` to install Claude Code skills
- [ ] Hand-author *one* composition matching the draft `1777849285` structure:
  - 3 b-roll segments with Ken Burns transforms (CSS/GSAP)
  - Voiceover audio track
  - Burned-in captions (HTML overlay)
  - End card
- [ ] Render at 1080×1920, 30fps, target ~70s
- [ ] Compare side-by-side vs current Ken Burns output
- [ ] **Go/no-go decision** before Phase 1

**Success criteria:** matches or exceeds current visual quality, render completes in ≤2× current ffmpeg time, no visible artifacts.

### Phase 1 — Composition Generator (1-2 days)
**Goal:** Replace `assemble.py` with `compose.py` that emits a HyperFrames composition from a draft.

- [ ] New module: `pipeline/compose.py`
  - Inputs: draft.json, broll paths, voiceover path, captions.json
  - Output: `composition.html` + asset symlinks
- [ ] Templates:
  - `templates/short.html.j2` — Jinja2 template for a UAVHQ Short
  - `templates/ken_burns.gsap.js` — GSAP timeline factory for Ken Burns
  - `templates/captions.css` — caption styling (matches current ass styling)
- [ ] `pipeline/render.py` — wraps `npx hyperframes render`
  - Runs render in subprocess
  - Captures stdout/stderr to log
  - Validates output resolution/fps/duration
  - Returns video path
- [ ] Update `pipeline/__main__.py` produce flow:
  - `compose` stage replaces `assemble` stage
  - State migration: rename `assemble` → `render` in state.json
- [ ] Keep old `assemble.py` for rollback (rename to `assemble_legacy.py`)

### Phase 2 — Cleanup (0.5 day)
- [ ] Remove `veo.py`, `prompt_builder.py` Veo functions (or move to `legacy/`)
- [ ] Remove `veo_cache/` cleanup logic
- [ ] Update `state.py` STAGES tuple (drop `veo_clip`)
- [ ] Update `docs/` — replace Veo strategy doc with HyperFrames composition guide
- [ ] Update protocol/SOP docs in `creative/uavhq-video-publishing` skill

### Phase 3 — Validation (0.5 day)
- [ ] Run 3 test shorts end-to-end (private upload)
- [ ] Verify against `sage-tester` skill (brand audit, quality gate)
- [ ] Confirm cost reduction (no more Veo $$$)
- [ ] Cron-driven test cycle for 1 week before going public

### Phase 4 — Long-form (later)
HyperFrames also enables the long-form UAVHQ video pipeline (`creative/uavhq-video-publishing`). Once Shorts are stable, extend the composition templates for 5-15 min long-form videos. This is where HyperFrames *really* pays off vs ffmpeg — multi-shot videos with lower thirds, B-roll cuts, branded transitions become trivial.

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| HyperFrames render slower than ffmpeg concat | Acceptable up to ~2× — measured in Phase 0 spike. If slower, parallelize across cron jobs. |
| Headless Chrome flaky on macOS | Run in Docker (HyperFrames ships a Dockerfile). Adds setup but bulletproof. |
| New dependency surface (Node, Puppeteer, Chrome) | Pin versions. Document in `_publishing-core/README`. CI for the render layer specifically. |
| Caption timing harder to debug in HTML vs ass | Keep captions.json as canonical timing source. HTML renderer is just a view. |
| HeyGen abandons project | 14.1k stars, 617 commits, active 6 hours ago. Apache 2.0 — we can fork. Low risk. |

---

## Cost Comparison

| Layer | Before (Path B) | Before (Path A) | After (HyperFrames) |
|-------|-----------------|-----------------|---------------------|
| B-roll images | ~$0.30 | ~$0.30 | ~$0.30 (unchanged) |
| Voiceover | ~$0.10 | ~$0.10 | ~$0.10 (unchanged) |
| Veo clips | $6.40 (2× 8s) | $0 | $0 |
| Render compute | negligible (ffmpeg) | negligible | negligible (local Chrome) |
| **Per Short total** | **~$6.80** | **~$0.40** | **~$0.40** |

We were going to swallow $6.80/Short for cinematic motion and the Path B architecture didn't deliver. HyperFrames keeps the $0.40 cost AND opens cleaner motion (CSS/GSAP) than ffmpeg zoompan.

---

## Open Questions

1. **Skills install location:** does `npx skills add heygen-com/hyperframes` write to `~/.hermes/skills/` or to project `.claude/`? Need to verify it doesn't clobber our skill organization.
2. **Audio mixing:** HyperFrames handles `<audio>` elements. Do we need separate ffmpeg post-processing for ducking/normalization, or can GSAP volume timelines handle it?
3. **Long-form extension:** is one composition template flexible enough for both Shorts (≤60s vertical) and long-form (5-15 min horizontal), or do we maintain two?

---

## Success Definition

This migration succeeds when:
- One command (`python -m pipeline produce --draft N`) reliably produces a publish-ready MP4 with no visible artifacts
- No more concat-boundary bugs in 30 consecutive runs
- Per-Short cost stays at ~$0.40
- A new motion style (e.g., bouncy captions, animated lower-third) takes <30 min to add via composition template edit

---

## References

- Repo: https://github.com/heygen-com/hyperframes
- Docs: https://hyperframes.heygen.com/introduction
- Catalog: https://hyperframes.heygen.com/catalog
- Hyperframes vs Remotion: https://hyperframes.heygen.com/guides/hyperframes-vs-remotion
- Triggering failure mode (Path B drift): see `~/.youtube-shorts-pipeline/media/work_1777849285_en/` and session log 2026-05-03
