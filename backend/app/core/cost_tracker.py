"""LLM cost tracking and budget enforcement.

Tracks token usage and costs per provider/model/book/chapter.
Enforces cost ceilings to prevent runaway spending.
Uses pre-aggregated counters for O(1) lookups and asyncio.Lock for safety.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger(__name__)

# Cost per 1M tokens (input/output) as of Feb 2026
MODEL_COSTS: dict[str, tuple[float, float]] = {
    # (input_per_1M, output_per_1M)
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o-2024-11-20": (2.50, 10.00),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.0-flash": (0.10, 0.40),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "voyage-3.5": (0.06, 0.0),  # embeddings: input only
    "BAAI/bge-m3": (0.0, 0.0),  # local embeddings: free
    "rerank-v3.5": (0.0, 0.0),  # Cohere rerank: per-search pricing
}


@dataclass
class CostEntry:
    """Single cost tracking entry."""

    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    operation: str  # extraction, reconciliation, chat, embedding, rerank
    book_id: str | None = None
    chapter: int | None = None


@dataclass
class CostTracker:
    """Tracks accumulated costs with budget enforcement.

    Uses pre-aggregated counters for O(1) lookups and asyncio.Lock
    for async safety. Recent entries are kept for summary/admin, but
    aggregated totals are the source of truth for ceiling checks.
    """

    ceiling_per_chapter: float = 0.50
    ceiling_per_book: float = 50.00
    entries: list[CostEntry] = field(default_factory=list)
    _total: float = field(default=0.0, repr=False)
    _by_book: dict[str, float] = field(default_factory=dict, repr=False)
    _by_chapter: dict[tuple[str, int], float] = field(default_factory=dict, repr=False)
    _by_provider: dict[str, float] = field(default_factory=dict, repr=False)
    _by_operation: dict[str, float] = field(default_factory=dict, repr=False)
    _by_model: dict[str, float] = field(default_factory=dict, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    @property
    def total_cost(self) -> float:
        return self._total

    def cost_for_book(self, book_id: str) -> float:
        return self._by_book.get(book_id, 0.0)

    def cost_for_chapter(self, book_id: str, chapter: int) -> float:
        return self._by_chapter.get((book_id, chapter), 0.0)

    async def record(
        self,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        operation: str,
        book_id: str | None = None,
        chapter: int | None = None,
    ) -> CostEntry:
        """Record a cost entry and return it (async-safe)."""
        cost = calculate_cost(model, input_tokens, output_tokens)
        entry = CostEntry(
            model=model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            operation=operation,
            book_id=book_id,
            chapter=chapter,
        )

        async with self._lock:
            self.entries.append(entry)
            self._total += cost
            if book_id:
                self._by_book[book_id] = self._by_book.get(book_id, 0.0) + cost
            if book_id and chapter is not None:
                key = (book_id, chapter)
                self._by_chapter[key] = self._by_chapter.get(key, 0.0) + cost
            self._by_provider[provider] = self._by_provider.get(provider, 0.0) + cost
            self._by_operation[operation] = self._by_operation.get(operation, 0.0) + cost
            self._by_model[model] = self._by_model.get(model, 0.0) + cost

        logger.info(
            "cost_recorded",
            model=model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost, 6),
            operation=operation,
            book_id=book_id,
            chapter=chapter,
            total_cost=round(self._total, 4),
        )
        return entry

    def check_chapter_ceiling(self, book_id: str, chapter: int) -> bool:
        """Check if chapter cost ceiling is exceeded. Returns True if OK."""
        cost = self.cost_for_chapter(book_id, chapter)
        if cost >= self.ceiling_per_chapter:
            logger.error(
                "cost_ceiling_exceeded",
                level="chapter",
                book_id=book_id,
                chapter=chapter,
                cost=round(cost, 4),
                ceiling=self.ceiling_per_chapter,
            )
            return False
        return True

    def check_book_ceiling(self, book_id: str) -> bool:
        """Check if book cost ceiling is exceeded. Returns True if OK."""
        cost = self.cost_for_book(book_id)
        if cost >= self.ceiling_per_book:
            logger.error(
                "cost_ceiling_exceeded",
                level="book",
                book_id=book_id,
                cost=round(cost, 4),
                ceiling=self.ceiling_per_book,
            )
            return False
        return True

    def summary(self) -> dict:
        """Return cost summary by provider and operation."""
        return {
            "total_cost_usd": round(self._total, 4),
            "total_entries": len(self.entries),
            "by_provider": {k: round(v, 4) for k, v in self._by_provider.items()},
            "by_operation": {k: round(v, 4) for k, v in self._by_operation.items()},
            "by_model": {k: round(v, 4) for k, v in self._by_model.items()},
        }


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in USD for a given model and token count."""
    costs = MODEL_COSTS.get(model)
    if costs is None:
        # Try partial match
        for key, val in MODEL_COSTS.items():
            if key in model or model in key:
                costs = val
                break
    if costs is None:
        logger.warning("cost_unknown_model", model=model)
        # Default to GPT-4o pricing as conservative estimate
        costs = MODEL_COSTS["gpt-4o"]

    input_cost = (input_tokens / 1_000_000) * costs[0]
    output_cost = (output_tokens / 1_000_000) * costs[1]
    return input_cost + output_cost


_tiktoken_encoder: object | None = None


def _get_tiktoken_encoder() -> object:
    """Lazy-load and cache the tiktoken encoder."""
    global _tiktoken_encoder  # noqa: PLW0603
    if _tiktoken_encoder is None:
        import tiktoken

        _tiktoken_encoder = tiktoken.encoding_for_model("gpt-4o")
    return _tiktoken_encoder


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens for a text using tiktoken.

    Falls back to character-based estimation if model not supported.
    Uses a cached encoder for performance.
    """
    try:
        encoder = _get_tiktoken_encoder()
        return len(encoder.encode(text))  # type: ignore[union-attr]
    except Exception:
        # Rough estimation: ~4 chars per token for English
        return len(text) // 4
