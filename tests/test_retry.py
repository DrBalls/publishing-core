"""Tests for publishing_core.retry."""
import pytest

from publishing_core.retry import with_retry


def test_succeeds_first_try():
    calls = []

    @with_retry(max_retries=3, base_delay=0.01)
    def f():
        calls.append(1)
        return "ok"

    assert f() == "ok"
    assert len(calls) == 1


def test_retries_on_failure():
    calls = []

    @with_retry(max_retries=3, base_delay=0.01)
    def f():
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("transient")
        return "ok"

    assert f() == "ok"
    assert len(calls) == 3


def test_raises_after_max_retries():
    @with_retry(max_retries=2, base_delay=0.01)
    def f():
        raise ConnectionError("nope")

    with pytest.raises(ConnectionError, match="nope"):
        f()


def test_retry_on_filter_lets_other_exceptions_through():
    calls = []

    @with_retry(max_retries=3, base_delay=0.01, retry_on=(ConnectionError,))
    def f():
        calls.append(1)
        raise ValueError("not retriable")

    with pytest.raises(ValueError):
        f()
    assert len(calls) == 1  # not retried


def test_retry_on_specific_exception():
    calls = []

    @with_retry(max_retries=3, base_delay=0.01, retry_on=(ConnectionError, TimeoutError))
    def f():
        calls.append(1)
        if len(calls) < 2:
            raise TimeoutError("retry me")
        return "ok"

    assert f() == "ok"
    assert len(calls) == 2


def test_preserves_function_metadata():
    @with_retry()
    def my_function():
        """My docstring."""
        return 1

    assert my_function.__name__ == "my_function"
    assert my_function.__doc__ == "My docstring."
