"""Async rate limiting per LLM provider.

Uses aiolimiter for token-bucket rate limiting + asyncio.Semaphore for concurrency.
Each provider has its own limiter to respect API rate limits.
"""

from __future__ import annotations

from aiolimiter import AsyncLimiter

from app.core.logging import get_logger

logger = get_logger(__name__)


class ProviderRateLimiter:
    """Rate limiter for a specific LLM provider.

    Combines:
    - Token bucket rate limiting (requests per time window)
    - Concurrency semaphore (max parallel requests)
    """

    def __init__(
        self,
        name: str,
        max_rate: float,
        time_period: float = 60.0,
        max_concurrent: int = 10,
    ) -> None:
        """Initialize rate limiter.

        Args:
            name: Provider name for logging.
            max_rate: Maximum requests per time_period.
            time_period: Time window in seconds.
            max_concurrent: Maximum concurrent requests.
        """
        self.name = name
        self.limiter = AsyncLimiter(max_rate, time_period)
        self.max_concurrent = max_concurrent
        self._active = 0

    async def acquire(self) -> None:
        """Acquire rate limit token. Blocks until available."""
        await self.limiter.acquire()
        self._active += 1
        if self._active > self.max_concurrent * 0.8:
            logger.info(
                "rate_limiter_high_concurrency",
                provider=self.name,
                active=self._active,
                max_concurrent=self.max_concurrent,
            )

    def release(self) -> None:
        """Release concurrency slot."""
        self._active = max(0, self._active - 1)

    @property
    def active_requests(self) -> int:
        return self._active


# --- Provider Rate Limiters (configured per provider limits) ---

# OpenAI: 500 RPM for GPT-4o-mini, 60 RPM for GPT-4o
openai_limiter = ProviderRateLimiter("openai", max_rate=200, time_period=60, max_concurrent=20)

# Gemini: 1000 RPM for Flash
gemini_limiter = ProviderRateLimiter("gemini", max_rate=500, time_period=60, max_concurrent=20)

# Anthropic: 50 RPM default
anthropic_limiter = ProviderRateLimiter("anthropic", max_rate=40, time_period=60, max_concurrent=10)

# Voyage: 300 RPM
voyage_limiter = ProviderRateLimiter("voyage", max_rate=200, time_period=60, max_concurrent=15)

# Cohere: 100 RPM
cohere_limiter = ProviderRateLimiter("cohere", max_rate=80, time_period=60, max_concurrent=10)


def get_limiter(provider: str) -> ProviderRateLimiter:
    """Get rate limiter for a provider name."""
    limiters = {
        "openai": openai_limiter,
        "gemini": gemini_limiter,
        "anthropic": anthropic_limiter,
        "voyage": voyage_limiter,
        "cohere": cohere_limiter,
    }
    limiter = limiters.get(provider)
    if limiter is None:
        logger.warning("rate_limiter_unknown_provider", provider=provider)
        return openai_limiter  # fallback
    return limiter
