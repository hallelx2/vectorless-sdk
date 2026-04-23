from __future__ import annotations

import asyncio
import random
import time
from typing import Callable, TypeVar, Awaitable

from vectorless.errors import VectorlessError, RateLimitError

T = TypeVar("T")


def _jitter() -> float:
    """Random jitter between 0 and 200ms to prevent thundering herd."""
    return random.random() * 0.2


def sync_retry(
    fn: Callable[[], T],
    max_retries: int = 3,
    retry_delay: float = 0.5,
) -> T:
    """Execute ``fn`` with retries and exponential backoff (synchronous)."""
    last_error: BaseException | None = None

    for attempt in range(max_retries + 1):
        try:
            return fn()
        except VectorlessError as e:
            last_error = e

            # Exhausted attempts
            if attempt >= max_retries:
                raise

            # Rate limit: respect Retry-After
            if e.status == 429:
                delay = (
                    e.retry_after  # type: ignore[union-attr]
                    if isinstance(e, RateLimitError) and e.retry_after is not None
                    else retry_delay * (2**attempt)
                )
                time.sleep(delay + _jitter())
                continue

            # Don't retry client errors (except 408 timeout and 429 rate limit)
            if 400 <= e.status < 500 and e.status not in (408, 429):
                raise

            # Retry 5xx, timeouts
            time.sleep(retry_delay * (2**attempt) + _jitter())

        except Exception as e:
            last_error = e
            if attempt >= max_retries:
                raise
            time.sleep(retry_delay * (2**attempt) + _jitter())

    raise last_error  # type: ignore[misc]


async def async_retry(
    fn: Callable[[], Awaitable[T]],
    max_retries: int = 3,
    retry_delay: float = 0.5,
) -> T:
    """Execute ``fn`` with retries and exponential backoff (asynchronous)."""
    last_error: BaseException | None = None

    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except VectorlessError as e:
            last_error = e

            if attempt >= max_retries:
                raise

            if e.status == 429:
                delay = (
                    e.retry_after  # type: ignore[union-attr]
                    if isinstance(e, RateLimitError) and e.retry_after is not None
                    else retry_delay * (2**attempt)
                )
                await asyncio.sleep(delay + _jitter())
                continue

            if 400 <= e.status < 500 and e.status not in (408, 429):
                raise

            await asyncio.sleep(retry_delay * (2**attempt) + _jitter())

        except Exception as e:
            last_error = e
            if attempt >= max_retries:
                raise
            await asyncio.sleep(retry_delay * (2**attempt) + _jitter())

    raise last_error  # type: ignore[misc]
