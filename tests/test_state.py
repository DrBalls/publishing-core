"""Tests for publishing_core.state."""
import json

import pytest

from publishing_core.state import PipelineState


@pytest.fixture
def state(tmp_path):
    p = tmp_path / "state.json"
    return PipelineState(path=p, stages=["a", "b", "c"])


def test_initial_all_pending(state):
    assert state.first_pending() == "a"
    assert not state.all_done()
    assert state.is_pending("a")


def test_complete_stage(state):
    state.complete_stage("a", artifacts={"path": "/tmp/x.mp4"})
    assert state.is_done("a")
    assert not state.is_pending("a")
    assert state.get_artifact("a", "path") == "/tmp/x.mp4"


def test_first_pending_advances(state):
    state.complete_stage("a")
    assert state.first_pending() == "b"
    state.complete_stage("b")
    assert state.first_pending() == "c"
    state.complete_stage("c")
    assert state.first_pending() is None
    assert state.all_done()


def test_save_and_load_roundtrip(tmp_path):
    p = tmp_path / "rt.json"
    s = PipelineState(path=p, stages=["x", "y"])
    s.complete_stage("x", artifacts={"out": "/tmp/x"})
    s.set_meta("run_id", "run-42")
    s.save()

    s2 = PipelineState.load(p)
    assert s2.is_done("x")
    assert s2.is_pending("y")
    assert s2.get_artifact("x", "out") == "/tmp/x"
    assert s2.get_meta("run_id") == "run-42"


def test_load_creates_fresh_when_missing(tmp_path):
    p = tmp_path / "fresh.json"
    s = PipelineState.load(p, stages=["a", "b"])
    assert s.first_pending() == "a"


def test_load_missing_no_stages_raises(tmp_path):
    p = tmp_path / "no.json"
    with pytest.raises(ValueError, match="does not exist"):
        PipelineState.load(p)


def test_fail_stage(state):
    state.fail_stage("b", error="ffmpeg returned 1")
    assert state.is_failed("b")
    assert not state.is_done("b")
    # Failed stages should still be picked up by first_pending so the caller can retry
    state.complete_stage("a")
    assert state.first_pending() == "b"


def test_reset(state):
    state.complete_stage("a")
    state.complete_stage("b")
    state.reset()
    assert state.first_pending() == "a"
    assert state.stages == ["a", "b", "c"]


def test_summary_format(state):
    state.complete_stage("a")
    state.fail_stage("b", "oops")
    s = state.summary()
    assert "[✓] a" in s
    assert "[✗] b" in s
    assert "[·] c" in s


def test_save_creates_parent_dirs(tmp_path):
    p = tmp_path / "deep" / "nested" / "state.json"
    s = PipelineState(path=p, stages=["a"])
    s.save()
    assert p.exists()
    assert json.loads(p.read_text())["stages"] == ["a"]
