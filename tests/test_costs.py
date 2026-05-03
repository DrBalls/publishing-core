"""Tests for publishing_core.costs."""
import pytest

from publishing_core.costs import CostLedger, open_ledger


@pytest.fixture
def ledger(tmp_path):
    db = tmp_path / "test-ledger.db"
    with CostLedger(db) as l:
        yield l


def test_log_anthropic_tokens(ledger):
    cost = ledger.log(
        project="test",
        provider="anthropic",
        operation="messages.create",
        input_tokens=1_000_000,
        output_tokens=500_000,
        model="claude-sonnet-4-5",
    )
    # 1M input * $3 + 0.5M output * $15 = $3 + $7.5 = $10.50
    assert cost == pytest.approx(10.50, abs=0.01)


def test_log_haiku_cheaper(ledger):
    cost = ledger.log(
        project="test",
        provider="anthropic",
        operation="messages.create",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        model="claude-haiku-4-5",
    )
    # 1M input * $1 + 1M output * $5 = $6.00
    assert cost == pytest.approx(6.0, abs=0.01)


def test_log_image_pricing(ledger):
    cost = ledger.log(
        project="test",
        provider="gemini",
        operation="image.generate",
        images=3,
        model="gemini-2.5-flash-image",
    )
    assert cost == pytest.approx(0.039 * 3, abs=0.001)


def test_log_unknown_model_defaults_zero(ledger):
    cost = ledger.log(
        project="test",
        provider="anthropic",
        operation="messages.create",
        input_tokens=1000,
        output_tokens=500,
        model="claude-future-9000",
    )
    assert cost == 0.0  # unknown model = no pricing data


def test_log_custom_cost_override(ledger):
    cost = ledger.log(
        project="test",
        provider="custom",
        operation="weird.api",
        custom_cost_usd=0.42,
    )
    assert cost == 0.42


def test_summary_by_project(ledger):
    ledger.log(project="uavhq", provider="anthropic", operation="messages.create",
               input_tokens=1_000_000, model="claude-haiku-4-5")
    ledger.log(project="uavhq", provider="anthropic", operation="messages.create",
               input_tokens=2_000_000, model="claude-haiku-4-5")
    ledger.log(project="other", provider="anthropic", operation="messages.create",
               input_tokens=1_000_000, model="claude-sonnet-4-5")

    s = ledger.summary_by_project("uavhq", since_days=1)
    assert s["project"] == "uavhq"
    assert s["total_usd"] == pytest.approx(3.0, abs=0.01)  # 3M * $1/M
    assert len(s["breakdown"]) == 1


def test_summary_by_run(ledger):
    ledger.log(project="uavhq", run_id="run-A", provider="anthropic",
               operation="messages.create", input_tokens=1_000_000,
               model="claude-haiku-4-5")
    ledger.log(project="uavhq", run_id="run-A", provider="gemini",
               operation="image.generate", images=2,
               model="gemini-2.5-flash-image")
    ledger.log(project="uavhq", run_id="run-B", provider="anthropic",
               operation="messages.create", input_tokens=500_000,
               model="claude-haiku-4-5")

    s = ledger.summary_by_run("run-A")
    assert s["run_id"] == "run-A"
    # 1M * $1/M (haiku input) + 2 * $0.039 (images) = $1 + $0.078 = $1.078
    assert s["total_usd"] == pytest.approx(1.078, abs=0.01)
    assert len(s["breakdown"]) == 2


def test_open_ledger_context_manager(tmp_path):
    db = tmp_path / "ctx.db"
    with open_ledger(db) as l:
        l.log(project="t", provider="anthropic", operation="x",
              input_tokens=1000, model="claude-haiku-4-5")
    # Re-open; data should persist
    with open_ledger(db) as l:
        s = l.summary_by_project("t", since_days=1)
        assert s["total_usd"] > 0


def test_outside_context_raises(tmp_path):
    l = CostLedger(tmp_path / "x.db")
    with pytest.raises(RuntimeError, match="not entered"):
        l.log(project="t", provider="anthropic", operation="x")
