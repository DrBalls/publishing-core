"""Cost-tracked wrappers around upstream API clients.

Use these instead of raw clients so every call lands in the cost ledger:

    from publishing_core.tracked_clients import TrackedAnthropic

    client = TrackedAnthropic(project="uavhq", run_id="san-diego-anomaly")
    msg = client.messages.create(model="claude-sonnet-4-5", ...)
    # Cost is logged automatically.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Optional

from publishing_core.auth import get_anthropic_client
from publishing_core.costs import CostLedger, DEFAULT_DB_PATH


class TrackedAnthropic:
    """Wraps anthropic.Anthropic with cost-tracked ``messages.create``.

    Logs every call to the cost ledger with provider='anthropic',
    operation='messages.create', and the model + token counts from the response.
    """

    def __init__(
        self,
        *,
        project: str,
        run_id: Optional[str] = None,
        ledger_db: Optional[str] = None,
    ):
        self._client = get_anthropic_client()
        self.project = project
        self.run_id = run_id
        self._ledger_db = ledger_db or str(DEFAULT_DB_PATH)
        self.messages = _AnthropicMessages(self)

    @property
    def raw(self):
        """Escape hatch — return the underlying anthropic client."""
        return self._client


class _AnthropicMessages:
    def __init__(self, parent: TrackedAnthropic):
        self._parent = parent

    def create(self, **kwargs) -> Any:
        client = self._parent._client
        response = client.messages.create(**kwargs)
        # Best-effort cost logging — never raise on accounting failure
        try:
            usage = getattr(response, "usage", None)
            if usage is not None:
                with CostLedger(self._parent._ledger_db) as ledger:
                    ledger.log(
                        project=self._parent.project,
                        run_id=self._parent.run_id,
                        provider="anthropic",
                        operation="messages.create",
                        input_tokens=getattr(usage, "input_tokens", 0) or 0,
                        output_tokens=getattr(usage, "output_tokens", 0) or 0,
                        model=kwargs.get("model", ""),
                    )
        except Exception:
            pass  # accounting must never break the user's call
        return response


def log_gemini_image(
    *,
    project: str,
    run_id: Optional[str],
    model: str,
    images: int = 1,
    ledger_db: Optional[str] = None,
) -> float:
    """Log a Gemini image-gen call to the ledger. Returns USD cost.

    Pure helper — Gemini's client lib is async/streamy enough that wrapping the
    whole thing isn't worth it. Call this immediately after a successful
    ``client.models.generate_content(...)`` for image gen.
    """
    db = ledger_db or str(DEFAULT_DB_PATH)
    try:
        with CostLedger(db) as ledger:
            return ledger.log(
                project=project,
                run_id=run_id,
                provider="gemini",
                operation="image.generate",
                images=images,
                model=model,
            )
    except Exception:
        return 0.0


def log_elevenlabs_tts(
    *,
    project: str,
    run_id: Optional[str],
    model: str,
    characters: int,
    ledger_db: Optional[str] = None,
) -> float:
    """Log an ElevenLabs TTS call to the ledger. Returns USD cost."""
    db = ledger_db or str(DEFAULT_DB_PATH)
    try:
        with CostLedger(db) as ledger:
            return ledger.log(
                project=project,
                run_id=run_id,
                provider="elevenlabs",
                operation="text_to_speech",
                characters=characters,
                model=model,
            )
    except Exception:
        return 0.0


@contextmanager
def tracked_run(project: str, run_id: str):
    """Context manager that yields a TrackedAnthropic + helper logger fns.

    Usage:
        with tracked_run("uavhq", "san-diego-short") as t:
            msg = t.anthropic.messages.create(model="claude-sonnet-4-5", ...)
            t.log_image("gemini-2.5-flash-image", images=5)
            t.log_tts("eleven_turbo_v2_5", characters=900)
    """
    class _Tracked:
        def __init__(self):
            self.anthropic = TrackedAnthropic(project=project, run_id=run_id)

        def log_image(self, model: str, images: int = 1) -> float:
            return log_gemini_image(project=project, run_id=run_id, model=model, images=images)

        def log_tts(self, model: str, characters: int) -> float:
            return log_elevenlabs_tts(project=project, run_id=run_id, model=model, characters=characters)

    yield _Tracked()
