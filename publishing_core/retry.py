"""Exponential backoff retry decorator.

Lifted from ``youtube-shorts-pipeline/pipeline/retry.py`` and made standalone
(uses stdlib logging instead of the shorts pipeline's bespoke logger).

Usage:
    from publishing_core.retry import with_retry

    @with_retry(max_retries=3, base_delay=2.0)
    def call_flaky_api():
        ...

    @with_retry(max_retries=5, base_delay=1.0, retry_on=(ConnectionError, TimeoutError))
    def call_network_api():
        ...
"""
from __future__ import annotations

import functools
import logging
import time
from typing import Callable, Type, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


def with_retry(
    max_retries: int = 3,
    base_delay: float = 2.0,
    retry_on: tuple[Type[BaseException], ...] = (Exception,),
):
    """Decorator: retry a function with exponential backoff on exception.

    Delays: ``base_delay * 2^attempt`` (default: 2s → 4s → 8s).

    Args:
        max_retries: Maximum retry attempts after the initial call (so
            ``max_retries=3`` means up to 4 total calls).
        base_delay: Initial delay in seconds.
        retry_on: Tuple of exception types to retry on. Other exceptions
            propagate immediately.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exc: BaseException | None = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retry_on as e:
                    last_exc = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(
                            "%s failed (attempt %d/%d): %s — retrying in %.1fs",
                            func.__name__, attempt + 1, max_retries + 1, e, delay,
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            "%s failed after %d attempts: %s",
                            func.__name__, max_retries + 1, e,
                        )
            assert last_exc is not None  # mypy hint
            raise last_exc
        return wrapper
    return decorator
