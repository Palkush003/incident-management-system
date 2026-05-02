"""
Retry utility with exponential backoff + jitter.
Uses tenacity for production-grade retry semantics.
Also includes a simple async Circuit Breaker.
"""
import asyncio
import random
import time
import structlog
from functools import wraps
from tenacity import (
    AsyncRetrying,
    RetryError,
    stop_after_attempt,
    wait_exponential,
    wait_random,
    retry_if_exception_type,
    before_sleep_log,
)
import logging

log = structlog.get_logger(__name__)


def async_retry(
    max_attempts: int = 3,
    min_wait: float = 0.5,
    max_wait: float = 10.0,
    exceptions: tuple = (Exception,),
):
    """Decorator for async functions with exponential backoff retry."""
    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(min=min_wait, max=max_wait) + wait_random(0, 0.5),
                retry=retry_if_exception_type(exceptions),
                reraise=True,
            ):
                with attempt:
                    return await fn(*args, **kwargs)
        return wrapper
    return decorator


class CircuitBreaker:
    """
    Simple async circuit breaker.
    States: CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing)
    """
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self._state = self.CLOSED
        self._failure_count = 0
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._last_failure_time: float | None = None

    @property
    def state(self) -> str:
        if self._state == self.OPEN:
            if time.monotonic() - (self._last_failure_time or 0) > self._recovery_timeout:
                self._state = self.HALF_OPEN
        return self._state

    async def call(self, fn, *args, **kwargs):
        if self.state == self.OPEN:
            raise RuntimeError("Circuit breaker is OPEN — call rejected")
        try:
            result = await fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise

    def _on_success(self):
        self._failure_count = 0
        self._state = self.CLOSED

    def _on_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self._failure_threshold:
            if self._state != self.OPEN:
                log.warning("circuit_breaker.opened", failures=self._failure_count)
            self._state = self.OPEN
