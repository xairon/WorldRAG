"""LLM cost tracking and budget enforcement.

Tracks token usage and costs per provider/model/book/chapter.
Enforces cost ceilings to prevent runaway spending.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import tiktoken

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

    Thread-safe for async usage (uses simple accumulation).
    """

    ceiling_per_chapter: float = 0.50
    ceiling_per_book: float = 50.00
    entries: list[CostEntry] = field(default_factory=list)

    @property
    def total_cost(self) -> float:
        return sum(e.cost_usd for e in self.entries)

    def cost_for_book(self, book_id: str) -> float:
        return sum(e.cost_usd for e in self.entries if e.book_id == book_id)

    def cost_for_chapter(self, book_id: str, chapter: int) -> float:
        return sum(
            e.cost_usd for e in self.entries if e.book_id == book_id and e.chapter == chapter
        )

    def record(
        self,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        operation: str,
        book_id: str | None = None,
        chapter: int | None = None,
    ) -> CostEntry:
        """Record a cost entry and return it."""
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
        self.entries.append(entry)

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
            total_cost=round(self.total_cost, 4),
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
        by_provider: dict[str, float] = {}
        by_operation: dict[str, float] = {}
        by_model: dict[str, float] = {}

        for entry in self.entries:
            by_provider[entry.provider] = by_provider.get(entry.provider, 0) + entry.cost_usd
            by_operation[entry.operation] = by_operation.get(entry.operation, 0) + entry.cost_usd
            by_model[entry.model] = by_model.get(entry.model, 0) + entry.cost_usd

        return {
            "total_cost_usd": round(self.total_cost, 4),
            "total_entries": len(self.entries),
            "by_provider": {k: round(v, 4) for k, v in by_provider.items()},
            "by_operation": {k: round(v, 4) for k, v in by_operation.items()},
            "by_model": {k: round(v, 4) for k, v in by_model.items()},
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


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens for a text using tiktoken.

    Falls back to character-based estimation if model not supported.
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except (KeyError, Exception):
        # Rough estimation: ~4 chars per token for English
        return len(text) // 4
