"""Generic resume-on-failure state machine for multi-stage pipelines.

Pattern lifted from ``youtube-shorts-pipeline/pipeline/state.py`` and made
generic so the long-form video render and any future pipelines can use it.

Usage:
    from publishing_core.state import PipelineState

    state = PipelineState.load("/tmp/run-state.json", stages=[
        "normalize", "mix_music", "encode_intro", "encode_outro",
        "upscale_main", "concat", "upload",
    ])

    if not state.is_done("normalize"):
        # ... do the work ...
        state.complete_stage("normalize", artifacts={"path": "/tmp/main-norm.mp4"})
        state.save()

    # Resume after crash:
    state = PipelineState.load("/tmp/run-state.json")  # picks up where it left off
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class PipelineState:
    """Tracks completion per named stage; persists to a JSON file.

    Each stage entry records: ``status`` (done/failed/pending), timestamp,
    optional artifact paths, and optional error string on failure.
    """

    def __init__(
        self,
        path: Optional[Path] = None,
        stages: Optional[list[str]] = None,
        data: Optional[dict] = None,
    ):
        self._path: Optional[Path] = Path(path) if path else None
        self._data: dict = data or {}
        if "stages" not in self._data:
            self._data["stages"] = list(stages or [])
        if "state" not in self._data:
            self._data["state"] = {}
        if "created_at" not in self._data:
            self._data["created_at"] = datetime.now(timezone.utc).isoformat()

    # ── Constructors ──────────────────────────────────────────────

    @classmethod
    def load(
        cls,
        path: Path | str,
        stages: Optional[list[str]] = None,
    ) -> "PipelineState":
        """Load from disk, or create fresh if file doesn't exist.

        If ``stages`` is provided AND the file exists, the loaded stages list
        is preserved (don't override after creation; reset() to start over).
        """
        p = Path(path).expanduser()
        if p.exists():
            data = json.loads(p.read_text())
            return cls(path=p, data=data)
        if stages is None:
            raise ValueError(
                f"State file {p} does not exist and no `stages` provided"
            )
        return cls(path=p, stages=stages)

    # ── Status queries ────────────────────────────────────────────

    @property
    def stages(self) -> list[str]:
        return list(self._data.get("stages", []))

    def is_done(self, stage: str) -> bool:
        return self._data["state"].get(stage, {}).get("status") == "done"

    def is_failed(self, stage: str) -> bool:
        return self._data["state"].get(stage, {}).get("status") == "failed"

    def is_pending(self, stage: str) -> bool:
        return stage not in self._data["state"]

    def all_done(self) -> bool:
        return all(self.is_done(s) for s in self.stages)

    def first_pending(self) -> Optional[str]:
        for s in self.stages:
            if not self.is_done(s):
                return s
        return None

    # ── Mutators ──────────────────────────────────────────────────

    def complete_stage(self, stage: str, artifacts: Optional[dict] = None) -> None:
        entry = {
            "status": "done",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if artifacts:
            entry["artifacts"] = artifacts
        self._data["state"][stage] = entry

    def fail_stage(self, stage: str, error: str = "") -> None:
        self._data["state"][stage] = {
            "status": "failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": error,
        }

    def get_artifact(self, stage: str, key: str, default: Any = None) -> Any:
        return (
            self._data["state"]
            .get(stage, {})
            .get("artifacts", {})
            .get(key, default)
        )

    def set_meta(self, key: str, value: Any) -> None:
        """Attach arbitrary run metadata (e.g. run_id, project, source path)."""
        self._data.setdefault("meta", {})[key] = value

    def get_meta(self, key: str, default: Any = None) -> Any:
        return self._data.get("meta", {}).get(key, default)

    def reset(self) -> None:
        """Clear all stage state. Stages list is preserved."""
        self._data["state"] = {}

    # ── Persistence ───────────────────────────────────────────────

    def save(self, path: Optional[Path | str] = None) -> Path:
        """Persist to JSON. Uses constructor path if none provided."""
        target = Path(path).expanduser() if path else self._path
        if target is None:
            raise ValueError("No path set for state file")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self._data, indent=2, ensure_ascii=False))
        self._path = target
        return target

    # ── Display ───────────────────────────────────────────────────

    def summary(self) -> str:
        """Human-readable per-stage status string."""
        marker = {"done": "✓", "failed": "✗", "pending": "·"}
        lines = []
        for stage in self.stages:
            entry = self._data["state"].get(stage, {})
            status = entry.get("status", "pending")
            lines.append(f"  [{marker.get(status, '?')}] {stage}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        n_done = sum(1 for s in self.stages if self.is_done(s))
        return f"<PipelineState {n_done}/{len(self.stages)} stages done>"
