"""Tests for publishing_core.tracked_clients."""
from unittest.mock import MagicMock, patch

import pytest

from publishing_core import tracked_clients


@pytest.fixture
def fake_anthropic(monkeypatch, tmp_path):
    """Patch get_anthropic_client + redirect ledger to a temp DB."""
    fake_response = MagicMock()
    fake_response.usage.input_tokens = 1_000_000
    fake_response.usage.output_tokens = 500_000

    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    monkeypatch.setattr(tracked_clients, "get_anthropic_client", lambda: fake_client)
    db = tmp_path / "ledger.db"
    return fake_client, fake_response, str(db)


def test_tracked_anthropic_logs_cost(fake_anthropic):
    fake_client, _, db = fake_anthropic
    t = tracked_clients.TrackedAnthropic(project="test", run_id="run-1", ledger_db=db)
    resp = t.messages.create(model="claude-sonnet-4-5", messages=[{"role": "user", "content": "hi"}])
    assert resp is not None

    # Verify call was forwarded to the underlying client
    fake_client.messages.create.assert_called_once()

    # Verify ledger row landed
    from publishing_core.costs import CostLedger
    with CostLedger(db) as l:
        s = l.summary_by_run("run-1")
    assert s["total_usd"] == pytest.approx(10.50, abs=0.01)  # 1M*3 + 0.5M*15 = 10.50


def test_log_gemini_image_returns_cost(tmp_path):
    db = str(tmp_path / "g.db")
    cost = tracked_clients.log_gemini_image(
        project="t", run_id="r1",
        model="gemini-2.5-flash-image", images=4, ledger_db=db,
    )
    assert cost == pytest.approx(0.039 * 4, abs=0.001)


def test_log_elevenlabs_tts_returns_cost(tmp_path):
    db = str(tmp_path / "el.db")
    cost = tracked_clients.log_elevenlabs_tts(
        project="t", run_id="r1",
        model="eleven_turbo_v2_5", characters=1_000_000, ledger_db=db,
    )
    assert cost == pytest.approx(30.0, abs=0.1)  # $30 per 1M chars


def test_accounting_never_breaks_caller(monkeypatch, tmp_path):
    """If the ledger explodes, the caller's API call still succeeds."""
    fake_response = MagicMock()
    fake_response.usage.input_tokens = 100
    fake_response.usage.output_tokens = 50
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    monkeypatch.setattr(tracked_clients, "get_anthropic_client", lambda: fake_client)
    # Make CostLedger raise on enter
    bad_db = "/this/path/does/not/exist/even/the/parent/cant/be/made/x.db"

    t = tracked_clients.TrackedAnthropic(project="t", run_id="r", ledger_db=bad_db)
    # Should not raise
    resp = t.messages.create(model="claude-sonnet-4-5", messages=[])
    assert resp is fake_response


def test_tracked_run_context(monkeypatch, tmp_path):
    fake_response = MagicMock()
    fake_response.usage.input_tokens = 100
    fake_response.usage.output_tokens = 50
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response
    monkeypatch.setattr(tracked_clients, "get_anthropic_client", lambda: fake_client)

    # Redirect default db to tmp
    monkeypatch.setattr(tracked_clients, "DEFAULT_DB_PATH", tmp_path / "ctx.db")

    with tracked_clients.tracked_run("uavhq", "ctx-run") as t:
        assert hasattr(t, "anthropic")
        assert callable(t.log_image)
        assert callable(t.log_tts)
