"""Tests for app.core.resilience — circuit breaker & retry patterns."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

from app.core.resilience import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    retry_llm_call,
)

# -- Circuit Breaker state machine ----------------------------------------


class TestCircuitBreakerClosed:

    async def test_initial_state_is_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    async def test_calls_function_when_closed(self):
        cb = CircuitBreaker("test")
        func = AsyncMock(return_value="ok")
        result = await cb.call(func)
        assert result == "ok"
        func.assert_called_once()

    async def test_success_resets_failure_count(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        # Cause some failures first
        failing = AsyncMock(side_effect=ValueError("fail"))
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(failing)
        assert cb.failure_count == 2

        # Now succeed
        success = AsyncMock(return_value="ok")
        await cb.call(success)
        assert cb.failure_count == 0

    async def test_trips_after_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        failing = AsyncMock(side_effect=RuntimeError("down"))
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await cb.call(failing)
        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerOpen:

    async def test_raises_immediately_when_open(self):
        cb = CircuitBreaker("test", failure_threshold=2)
        failing = AsyncMock(side_effect=RuntimeError("down"))
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(failing)
        assert cb.state == CircuitState.OPEN

        # Now it should raise without calling func
        fresh_func = AsyncMock(return_value="ok")
        with pytest.raises(CircuitBreakerOpenError):
            await cb.call(fresh_func)
        fresh_func.assert_not_called()

    async def test_error_contains_name(self):
        cb = CircuitBreaker("my_service", failure_threshold=1)
        failing = AsyncMock(side_effect=RuntimeError())
        with pytest.raises(RuntimeError):
            await cb.call(failing)
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            await cb.call(AsyncMock())
        assert exc_info.value.breaker_name == "my_service"

    async def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=60)
        failing = AsyncMock(side_effect=RuntimeError())
        with pytest.raises(RuntimeError):
            await cb.call(failing)
        assert cb.state == CircuitState.OPEN

        # Fast-forward time past recovery_timeout
        with patch.object(time, "monotonic", return_value=cb.last_failure_time + 61):
            success = AsyncMock(return_value="recovered")
            result = await cb.call(success)
            assert result == "recovered"
            # Should have transitioned through HALF_OPEN
            # After success, might still be HALF_OPEN (needs more successes)
            assert cb.state in (CircuitState.HALF_OPEN, CircuitState.CLOSED)


class TestCircuitBreakerHalfOpen:

    async def _make_half_open(self, cb: CircuitBreaker) -> None:
        """Helper to get a breaker into HALF_OPEN state."""
        failing = AsyncMock(side_effect=RuntimeError())
        for _ in range(cb.failure_threshold):
            with pytest.raises(RuntimeError):
                await cb.call(failing)
        assert cb.state == CircuitState.OPEN
        # Manually transition to half_open
        cb.state = CircuitState.HALF_OPEN
        cb.success_count = 0

    async def test_half_open_to_closed_after_successes(self):
        cb = CircuitBreaker("test", failure_threshold=2, half_open_max_calls=3)
        await self._make_half_open(cb)

        success = AsyncMock(return_value="ok")
        for _ in range(3):
            await cb.call(success)
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    async def test_half_open_to_open_on_failure(self):
        cb = CircuitBreaker("test", failure_threshold=2, half_open_max_calls=3)
        await self._make_half_open(cb)

        failing = AsyncMock(side_effect=RuntimeError("fail again"))
        with pytest.raises(RuntimeError):
            await cb.call(failing)
        assert cb.state == CircuitState.OPEN


# -- retry_llm_call -------------------------------------------------------


class TestRetryLlmCall:

    async def test_retries_on_timeout_error(self):
        call_count = 0

        @retry_llm_call(max_attempts=3)
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("timeout")
            return "ok"

        with patch("tenacity.nap.sleep", new_callable=AsyncMock):
            result = await flaky()
        assert result == "ok"
        assert call_count == 3

    async def test_retries_on_connection_error(self):
        call_count = 0

        @retry_llm_call(max_attempts=3)
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("refused")
            return "ok"

        with patch("tenacity.nap.sleep", new_callable=AsyncMock):
            result = await flaky()
        assert result == "ok"

    async def test_no_retry_on_value_error(self):
        """ValueError is not retried — raises immediately."""

        @retry_llm_call(max_attempts=3)
        async def bad():
            raise ValueError("bad input")

        with (
            pytest.raises(ValueError, match="bad input"),
            patch("tenacity.nap.sleep", new_callable=AsyncMock),
        ):
            await bad()

    async def test_max_attempts_exceeded(self):
        """After max_attempts, the error is reraised."""

        @retry_llm_call(max_attempts=2)
        async def always_fails():
            raise TimeoutError("always")

        with (
            pytest.raises(TimeoutError, match="always"),
            patch("tenacity.nap.sleep", new_callable=AsyncMock),
        ):
            await always_fails()
