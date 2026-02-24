"""Tests for app.core.cost_tracker — cost calculation & budget enforcement."""

from __future__ import annotations

import pytest

from app.core.cost_tracker import CostTracker, calculate_cost, count_tokens

# -- calculate_cost -------------------------------------------------------


class TestCalculateCost:
    """Tests for the calculate_cost function."""

    def test_exact_model_match_input(self):
        """gpt-4o: 1M input tokens -> $2.50."""
        cost = calculate_cost("gpt-4o", 1_000_000, 0)
        assert cost == pytest.approx(2.50)

    def test_exact_model_match_output(self):
        """gpt-4o: 1M output tokens -> $10.00."""
        cost = calculate_cost("gpt-4o", 0, 1_000_000)
        assert cost == pytest.approx(10.00)

    def test_combined_input_output(self):
        """gpt-4o-mini: mixed input+output."""
        # 2M input * 0.15/1M = 0.30 + 1M output * 0.60/1M = 0.60
        cost = calculate_cost("gpt-4o-mini", 2_000_000, 1_000_000)
        assert cost == pytest.approx(0.90)

    def test_partial_match_fallback(self):
        """claude-3-5-sonnet-20241022 matches via 'claude-3-5-sonnet' substring."""
        cost = calculate_cost("claude-3-5-sonnet-20241022", 1_000_000, 0)
        assert cost == pytest.approx(3.00)

    def test_unknown_model_defaults_to_gpt4o(self):
        """Unknown model falls back to gpt-4o rates."""
        cost = calculate_cost("unknown-model-xyz", 1_000_000, 0)
        assert cost == pytest.approx(2.50)

    def test_embedding_model_zero_output(self):
        """voyage-3.5: output rate is 0, so output tokens cost nothing."""
        cost = calculate_cost("voyage-3.5", 1_000_000, 500_000)
        assert cost == pytest.approx(0.06)

    def test_zero_tokens_zero_cost(self):
        cost = calculate_cost("gpt-4o", 0, 0)
        assert cost == 0.0


# -- count_tokens ---------------------------------------------------------


class TestCountTokens:
    """Tests for the count_tokens function."""

    def test_known_model_tiktoken(self):
        """Tiktoken path: result should be a positive int."""
        result = count_tokens("Hello world, this is a test.", "gpt-4o")
        assert isinstance(result, int)
        assert result > 0

    def test_unknown_model_uses_cached_encoder(self):
        """Unknown model uses cached gpt-4o encoder (not char fallback)."""
        text = "a" * 100
        result = count_tokens(text, "totally-unknown-model-xyz")
        assert isinstance(result, int)
        assert result > 0

    def test_empty_string(self):
        result = count_tokens("", "gpt-4o")
        assert result == 0


# -- CostTracker ----------------------------------------------------------


class TestCostTracker:
    """Tests for the CostTracker dataclass."""

    async def test_record_creates_entry(self):
        tracker = CostTracker()
        entry = await tracker.record(
            "gpt-4o-mini",
            "openai",
            1000,
            500,
            "extraction",
            book_id="b1",
            chapter=1,
        )
        assert len(tracker.entries) == 1
        assert entry.cost_usd > 0
        assert entry.model == "gpt-4o-mini"
        assert entry.book_id == "b1"

    async def test_total_cost_sums_entries(self):
        tracker = CostTracker()
        await tracker.record("gpt-4o-mini", "openai", 1_000_000, 0, "ext", book_id="b1")
        await tracker.record("gpt-4o-mini", "openai", 1_000_000, 0, "ext", book_id="b1")
        # Each is 0.15, total 0.30
        assert tracker.total_cost == pytest.approx(0.30)

    async def test_cost_for_book_filters(self):
        tracker = CostTracker()
        await tracker.record("gpt-4o-mini", "openai", 1_000_000, 0, "ext", book_id="b1")
        await tracker.record("gpt-4o-mini", "openai", 1_000_000, 0, "ext", book_id="b2")
        assert tracker.cost_for_book("b1") == pytest.approx(0.15)
        assert tracker.cost_for_book("b2") == pytest.approx(0.15)

    async def test_check_chapter_ceiling(self):
        tracker = CostTracker(ceiling_per_chapter=0.10)
        await tracker.record(
            "gpt-4o-mini",
            "openai",
            100_000,
            0,
            "ext",
            book_id="b1",
            chapter=1,
        )
        # Cost is tiny (0.015), under ceiling
        assert tracker.check_chapter_ceiling("b1", 1) is True

        # Push over ceiling
        await tracker.record(
            "gpt-4o",
            "openai",
            1_000_000,
            0,
            "ext",
            book_id="b1",
            chapter=1,
        )
        # Cost now >= 0.10
        assert tracker.check_chapter_ceiling("b1", 1) is False

    async def test_summary_structure(self):
        tracker = CostTracker()
        await tracker.record("gpt-4o-mini", "openai", 1000, 0, "extraction")
        await tracker.record("claude-3-5-sonnet", "anthropic", 1000, 0, "chat")
        s = tracker.summary()
        assert "total_cost_usd" in s
        assert "total_entries" in s
        assert s["total_entries"] == 2
        assert "by_provider" in s
        assert "openai" in s["by_provider"]
        assert "anthropic" in s["by_provider"]
        assert "by_operation" in s
        assert "extraction" in s["by_operation"]
        assert "by_model" in s
