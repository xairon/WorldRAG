"""Resilience patterns: circuit breaker, retry decorators, model fallbacks.

Provides production-grade error handling for LLM API calls.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.core.logging import get_logger

logger = get_logger(__name__)


# --- Circuit Breaker ---


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Circuit breaker for external service calls.

    Transitions:
        CLOSED → OPEN: After `failure_threshold` consecutive failures
        OPEN → HALF_OPEN: After `recovery_timeout` seconds
        HALF_OPEN → CLOSED: After `half_open_max_calls` successes
        HALF_OPEN → OPEN: On any failure
    """

    name: str
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_max_calls: int = 3

    state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    failure_count: int = field(default=0, init=False)
    success_count: int = field(default=0, init=False)
    last_failure_time: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    _half_open_in_flight: int = field(default=0, init=False)

    async def call[T](self, func: Any, *args: Any, **kwargs: Any) -> T:
        """Execute a function through the circuit breaker.

        Raises:
            CircuitBreakerOpenError: If the circuit is open.
        """
        async with self._lock:
            self._check_state_transition()

            if self.state == CircuitState.OPEN:
                logger.warning(
                    "circuit_breaker_open",
                    breaker=self.name,
                    recovery_in=self.recovery_timeout - (time.monotonic() - self.last_failure_time),
                )
                raise CircuitBreakerOpenError(self.name)

            if (
                self.state == CircuitState.HALF_OPEN
                and self._half_open_in_flight >= self.half_open_max_calls
            ):
                raise CircuitBreakerOpenError(self.name)

            if self.state == CircuitState.HALF_OPEN:
                self._half_open_in_flight += 1

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as exc:
            await self._on_failure(exc)
            raise
        finally:
            async with self._lock:
                if self._half_open_in_flight > 0:
                    self._half_open_in_flight -= 1

    def _check_state_transition(self) -> None:
        """Check if we should transition from OPEN to HALF_OPEN."""
        if self.state == CircuitState.OPEN:
            elapsed = time.monotonic() - self.last_failure_time
            if elapsed >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info("circuit_breaker_half_open", breaker=self.name)

    async def _on_success(self) -> None:
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.half_open_max_calls:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    logger.info("circuit_breaker_closed", breaker=self.name)
            else:
                self.failure_count = 0

    async def _on_failure(self, exc: Exception) -> None:
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.monotonic()

            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.warning(
                    "circuit_breaker_reopened",
                    breaker=self.name,
                    error=str(exc),
                )
            elif self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(
                    "circuit_breaker_tripped",
                    breaker=self.name,
                    failures=self.failure_count,
                    error=str(exc),
                )


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is in OPEN state."""

    def __init__(self, breaker_name: str) -> None:
        self.breaker_name = breaker_name
        super().__init__(f"Circuit breaker '{breaker_name}' is OPEN")


# --- Retry Decorators ---


def _log_retry(retry_state: RetryCallState) -> None:
    """Log retry attempts with context."""
    logger.warning(
        "retry_attempt",
        attempt=retry_state.attempt_number,
        wait=getattr(retry_state.next_action, "sleep", None),
        error=str(retry_state.outcome.exception()) if retry_state.outcome else None,
    )


def retry_llm_call(max_attempts: int = 3):
    """Retry decorator for LLM API calls with exponential backoff + jitter.

    Retries on rate limit errors and timeout errors.
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(initial=1, max=30, jitter=5),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        before_sleep=_log_retry,
        reraise=True,
    )


def retry_neo4j_write(max_attempts: int = 4):
    """Retry decorator for Neo4j write operations on transient errors.

    Catches DeadlockDetected and other TransientErrors from concurrent
    MERGE operations during parallel chapter processing.
    Uses jittered backoff to prevent thundering herd.
    """
    from neo4j.exceptions import TransientError

    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential_jitter(initial=0.2, max=10, jitter=2),
        retry=retry_if_exception_type(TransientError),
        before_sleep=_log_retry,
        reraise=True,
    )


# --- Provider Circuit Breakers (singletons) ---

openai_breaker = CircuitBreaker(name="openai", failure_threshold=5, recovery_timeout=60)
gemini_breaker = CircuitBreaker(name="gemini", failure_threshold=5, recovery_timeout=60)
anthropic_breaker = CircuitBreaker(name="anthropic", failure_threshold=5, recovery_timeout=60)
cohere_breaker = CircuitBreaker(name="cohere", failure_threshold=3, recovery_timeout=120)
voyage_breaker = CircuitBreaker(name="voyage", failure_threshold=3, recovery_timeout=120)
