# publishing-core

Shared Python primitives for the UAVHQ + Digital Splendor publishing pipelines.

## What's in here

- `publishing_core.auth` — Anthropic / Gemini / ElevenLabs credential chain (env → ~/.hermes/.env → Claude Max OAuth fallback)
- `publishing_core.models` — Single source of truth for model names per task (loads `models.yaml`)
- `publishing_core.embeds` — Templated HTML snippets (YouTube blog embed, etc.)

Future:
- `publishing_core.costs` — SQLite cost ledger
- `publishing_core.state` — Resume-on-failure pipeline state
- `publishing_core.retry` — Shared retry/backoff
- `publishing_core.distribution` — Cross-platform fan-out

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

## Versioning

Semver. Bump on any breaking API change. Consumers pin via `publishing-core==X.Y`.

---

*Created 2026-05-02 as Phase 1 of `~/.hermes/plans/2026-05-02-content-publishing-modernization.md`.*
