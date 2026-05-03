"""SQLite cost ledger for tracking API spend across publishing pipelines.

Stores one row per API call: provider, operation, units (tokens/seconds/images),
unit cost, total cost, and arbitrary metadata.

Usage:
    from publishing_core.costs import CostLedger

    with CostLedger() as ledger:
        ledger.log(
            project="uavhq",
            run_id="san-diego-anomaly",
            provider="anthropic",
            operation="messages.create",
            input_tokens=1234,
            output_tokens=567,
            model="claude-sonnet-4-5",
        )

    # Query later:
    ledger.summary_by_project("uavhq", since_days=7)
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

DEFAULT_DB_PATH = Path.home() / ".hermes" / "cost-ledger.db"

# Pricing table — USD per 1M tokens (as of 2026-05; update when pricing changes)
# Source: anthropic.com/pricing, ai.google.dev/pricing, elevenlabs.io/pricing
PRICING_PER_M_TOKENS: dict[str, dict[str, float]] = {
    # Anthropic — input + output per 1M tokens
    "claude-opus-4-7":   {"input": 15.00, "output": 75.00},
    "claude-opus-4-6":   {"input": 15.00, "output": 75.00},
    "claude-opus-4-5":   {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-7": {"input":  3.00, "output": 15.00},
    "claude-sonnet-4-6": {"input":  3.00, "output": 15.00},
    "claude-sonnet-4-5": {"input":  3.00, "output": 15.00},
    "claude-haiku-4-5":  {"input":  1.00, "output":  5.00},
    # Gemini
    "gemini-2.5-pro":         {"input": 1.25, "output":  10.00},
    "gemini-2.5-flash":       {"input": 0.30, "output":   2.50},
    "gemini-2.5-flash-image": {"input": 0.30, "output":  30.00},  # image gen — output priced per-image; this is approximate
}

# Per-image pricing (where applicable) — USD per image
PRICING_PER_IMAGE: dict[str, float] = {
    "gemini-2.5-flash-image": 0.039,    # 1K resolution
    "gemini-2.5-flash-image-2k": 0.039,
    "gemini-2.5-flash-image-4k": 0.039,
}

# Per-character pricing (ElevenLabs)
PRICING_PER_CHAR: dict[str, float] = {
    "eleven_turbo_v2_5":  0.00003,   # $30 per 1M chars
    "eleven_multilingual_v2": 0.00003,
}


@dataclass
class CostEntry:
    timestamp: str
    project: str
    run_id: Optional[str]
    provider: str
    operation: str
    units: float
    unit_cost_usd: float
    total_cost_usd: float
    metadata: dict[str, Any]


class CostLedger:
    """SQLite-backed ledger of API spend.

    Use as a context manager (auto-commits on exit) or call commit() manually.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS api_costs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp       TEXT NOT NULL,
        project         TEXT NOT NULL,
        run_id          TEXT,
        provider        TEXT NOT NULL,
        operation       TEXT NOT NULL,
        units           REAL NOT NULL,
        unit_cost_usd   REAL NOT NULL,
        total_cost_usd  REAL NOT NULL,
        metadata_json   TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_costs_timestamp ON api_costs(timestamp);
    CREATE INDEX IF NOT EXISTS idx_costs_project ON api_costs(project);
    CREATE INDEX IF NOT EXISTS idx_costs_run ON api_costs(run_id);
    """

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> "CostLedger":
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.executescript(self.SCHEMA)
        return self

    def __exit__(self, *_):
        if self._conn:
            self._conn.commit()
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("CostLedger not entered as context manager")
        return self._conn

    def log(
        self,
        *,
        project: str,
        provider: str,
        operation: str,
        run_id: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        characters: int = 0,
        images: int = 0,
        seconds: float = 0.0,
        model: Optional[str] = None,
        custom_cost_usd: Optional[float] = None,
        metadata: Optional[dict] = None,
    ) -> float:
        """Log an API call. Returns the computed total_cost_usd.

        For LLM calls: pass ``input_tokens`` + ``output_tokens`` + ``model``.
        For image gen: pass ``images`` + ``model``.
        For TTS:       pass ``characters`` + ``model``.
        Or pass ``custom_cost_usd`` to override pricing computation entirely.
        """
        meta = dict(metadata or {})
        if model:
            meta["model"] = model

        # Compute cost
        if custom_cost_usd is not None:
            total = custom_cost_usd
            units = input_tokens + output_tokens + characters + images
            unit_cost = total / units if units else total
        elif input_tokens or output_tokens:
            total = self._cost_for_tokens(model or "", input_tokens, output_tokens)
            units = input_tokens + output_tokens
            unit_cost = total / units if units else 0.0
            meta.update({"input_tokens": input_tokens, "output_tokens": output_tokens})
        elif images:
            unit_cost = PRICING_PER_IMAGE.get(model or "", 0.0)
            total = unit_cost * images
            units = images
            meta["images"] = images
        elif characters:
            unit_cost = PRICING_PER_CHAR.get(model or "", 0.0)
            total = unit_cost * characters
            units = characters
            meta["characters"] = characters
        else:
            total = 0.0
            unit_cost = 0.0
            units = 0.0

        ts = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO api_costs (timestamp, project, run_id, provider, operation, "
            "units, unit_cost_usd, total_cost_usd, metadata_json) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (ts, project, run_id, provider, operation,
             units, unit_cost, total, json.dumps(meta)),
        )
        return total

    @staticmethod
    def _cost_for_tokens(model: str, input_tokens: int, output_tokens: int) -> float:
        prices = PRICING_PER_M_TOKENS.get(model)
        if not prices:
            return 0.0
        return (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000

    def summary_by_project(
        self,
        project: str,
        since_days: int = 7,
    ) -> dict[str, Any]:
        """Aggregate stats for a project over the last N days."""
        since = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
        cur = self.conn.execute(
            "SELECT provider, operation, COUNT(*) as n, SUM(total_cost_usd) as total "
            "FROM api_costs WHERE project=? AND timestamp>=? "
            "GROUP BY provider, operation ORDER BY total DESC",
            (project, since),
        )
        rows = [
            {"provider": r[0], "operation": r[1], "calls": r[2], "total_usd": r[3]}
            for r in cur.fetchall()
        ]
        total = sum(r["total_usd"] for r in rows)
        return {"project": project, "since_days": since_days, "total_usd": total, "breakdown": rows}

    def summary_by_run(self, run_id: str) -> dict[str, Any]:
        """Aggregate stats for a single run_id (e.g. one video publish)."""
        cur = self.conn.execute(
            "SELECT provider, operation, COUNT(*) as n, SUM(total_cost_usd) as total "
            "FROM api_costs WHERE run_id=? GROUP BY provider, operation ORDER BY total DESC",
            (run_id,),
        )
        rows = [
            {"provider": r[0], "operation": r[1], "calls": r[2], "total_usd": r[3]}
            for r in cur.fetchall()
        ]
        return {"run_id": run_id, "total_usd": sum(r["total_usd"] for r in rows), "breakdown": rows}


@contextmanager
def open_ledger(db_path: Path | str = DEFAULT_DB_PATH) -> Iterator[CostLedger]:
    """Convenience: ``with open_ledger() as ledger: ledger.log(...)``."""
    with CostLedger(db_path) as ledger:
        yield ledger
