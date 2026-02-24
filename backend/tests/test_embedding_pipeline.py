"""Tests for the embedding pipeline service.

Validates batch embedding, partial failure handling, cost tracking,
and Neo4j write-back logic — all with mocked VoyageEmbedder and driver.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.embedding_pipeline import (
    EMBEDDING_BATCH_SIZE,
    EmbeddingResult,
    _write_embeddings,
    embed_book_chunks,
)

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_driver():
    """Mock Neo4j AsyncDriver with session context manager."""
    driver = MagicMock()
    session = AsyncMock()
    ctx_mgr = AsyncMock()
    ctx_mgr.__aenter__ = AsyncMock(return_value=session)
    ctx_mgr.__aexit__ = AsyncMock(return_value=False)
    driver.session.return_value = ctx_mgr
    return driver


@pytest.fixture
def mock_cost_tracker():
    """Mock CostTracker with async record method."""
    tracker = MagicMock()
    tracker.record = AsyncMock()
    return tracker


def _make_chunks(n: int, book_id: str = "book1") -> list[dict]:
    """Create n test chunk dicts."""
    return [
        {
            "chapter_id": f"{book_id}-ch{(i // 10) + 1}",
            "position": i % 10,
            "text": f"Test chunk text number {i}. " * 5,
        }
        for i in range(n)
    ]


def _fake_embeddings(n: int) -> list[list[float]]:
    """Create n fake 1024-dim embedding vectors."""
    return [[0.01 * (i + 1)] * 1024 for i in range(n)]


# ── TestEmbedBookChunks ──────────────────────────────────────────────────


class TestEmbedBookChunks:
    """Tests for the main embed_book_chunks function."""

    async def test_empty_chunks_returns_zero(self, mock_driver):
        result = await embed_book_chunks(mock_driver, "book1", [], None)
        assert isinstance(result, EmbeddingResult)
        assert result.embedded == 0
        assert result.failed == 0
        assert result.total_chunks == 0

    async def test_single_chunk_embeds_and_writes(self, mock_driver, mock_cost_tracker):
        chunks = _make_chunks(1)
        fake_emb = _fake_embeddings(1)

        with patch("app.services.embedding_pipeline.get_embedder") as mock_embedder_cls:
            instance = mock_embedder_cls.return_value
            instance.embed_texts = AsyncMock(return_value=fake_emb)

            result = await embed_book_chunks(
                mock_driver,
                "book1",
                chunks,
                mock_cost_tracker,
            )

        assert result.embedded == 1
        assert result.failed == 0
        assert result.total_tokens > 0
        assert result.cost_usd == 0.0  # local embeddings = free
        instance.embed_texts.assert_called_once()

    async def test_cost_not_tracked_for_local_provider(self, mock_driver, mock_cost_tracker):
        """Local embeddings (default) should NOT record cost."""
        chunks = _make_chunks(3)
        fake_emb = _fake_embeddings(3)

        with patch("app.services.embedding_pipeline.get_embedder") as mock_embedder_fn:
            instance = mock_embedder_fn.return_value
            instance.embed_texts = AsyncMock(return_value=fake_emb)

            await embed_book_chunks(
                mock_driver,
                "book1",
                chunks,
                mock_cost_tracker,
            )

        # Local provider = no cost tracking
        mock_cost_tracker.record.assert_not_called()

    async def test_cost_tracked_for_voyage_provider(self, mock_driver, mock_cost_tracker):
        """Voyage embeddings should record cost per batch."""
        chunks = _make_chunks(3)
        fake_emb = _fake_embeddings(3)

        with (
            patch("app.services.embedding_pipeline.get_embedder") as mock_embedder_fn,
            patch("app.services.embedding_pipeline.settings") as mock_settings,
        ):
            mock_settings.embedding_provider = "voyage"
            mock_settings.voyage_model = "voyage-3.5"
            mock_settings.embedding_model = "BAAI/bge-m3"
            instance = mock_embedder_fn.return_value
            instance.embed_texts = AsyncMock(return_value=fake_emb)

            await embed_book_chunks(
                mock_driver,
                "book1",
                chunks,
                mock_cost_tracker,
            )

        mock_cost_tracker.record.assert_called_once()
        call_kwargs = mock_cost_tracker.record.call_args.kwargs
        assert call_kwargs["model"] == "voyage-3.5"
        assert call_kwargs["provider"] == "voyage"
        assert call_kwargs["operation"] == "embedding"
        assert call_kwargs["book_id"] == "book1"

    async def test_partial_failure_continues(self, mock_driver):
        """First batch fails, second succeeds — pipeline continues."""
        # 256 chunks = 2 batches of 128
        chunks = _make_chunks(EMBEDDING_BATCH_SIZE * 2)

        call_count = 0

        async def side_effect(texts, input_type="document"):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Voyage API down")
            return _fake_embeddings(len(texts))

        with patch("app.services.embedding_pipeline.get_embedder") as mock_embedder_cls:
            instance = mock_embedder_cls.return_value
            instance.embed_texts = AsyncMock(side_effect=side_effect)

            result = await embed_book_chunks(mock_driver, "book1", chunks, None)

        assert result.failed == EMBEDDING_BATCH_SIZE
        assert result.embedded == EMBEDDING_BATCH_SIZE
        assert len(result.failed_keys) == EMBEDDING_BATCH_SIZE

    async def test_multiple_batches_boundary(self, mock_driver):
        """Verify batching at exactly EMBEDDING_BATCH_SIZE boundary."""
        n = EMBEDDING_BATCH_SIZE + 1  # 129 = 2 batches
        chunks = _make_chunks(n)

        with patch("app.services.embedding_pipeline.get_embedder") as mock_embedder_cls:
            instance = mock_embedder_cls.return_value
            instance.embed_texts = AsyncMock(
                side_effect=lambda texts, **kw: _fake_embeddings(len(texts)),
            )

            result = await embed_book_chunks(mock_driver, "book1", chunks, None)

        assert result.embedded == n
        assert result.failed == 0
        # embed_texts called twice: 128 + 1
        assert instance.embed_texts.call_count == 2

    async def test_local_cost_usd_is_zero(self, mock_driver):
        """Local embeddings should report zero cost."""
        chunks = _make_chunks(5)

        with patch("app.services.embedding_pipeline.get_embedder") as mock_embedder_fn:
            instance = mock_embedder_fn.return_value
            instance.embed_texts = AsyncMock(
                side_effect=lambda texts, **kw: _fake_embeddings(len(texts)),
            )

            result = await embed_book_chunks(mock_driver, "book1", chunks, None)

        assert result.cost_usd == 0.0
        assert result.total_tokens > 0


# ── TestWriteEmbeddings ──────────────────────────────────────────────────


class TestWriteEmbeddings:
    """Tests for the internal _write_embeddings function."""

    async def test_writes_correct_payload(self, mock_driver):
        batch = [
            {"chapter_id": "book1-ch1", "position": 0, "text": "hello"},
            {"chapter_id": "book1-ch1", "position": 1, "text": "world"},
        ]
        embeddings = [[0.1] * 1024, [0.2] * 1024]

        await _write_embeddings(mock_driver, batch, embeddings)

        # Verify session.run was called with UNWIND query
        session = mock_driver.session.return_value.__aenter__.return_value
        session.run.assert_called_once()
        call_args = session.run.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert "UNWIND $items AS item" in query
        assert "SET ck.embedding = item.embedding" in query
        assert len(params["items"]) == 2
        assert params["items"][0]["chapter_id"] == "book1-ch1"
        assert params["items"][0]["position"] == 0
        assert len(params["items"][0]["embedding"]) == 1024

    async def test_empty_batch_no_call(self, mock_driver):
        """Empty batch should still call run (UNWIND handles it)."""
        await _write_embeddings(mock_driver, [], [])

        session = mock_driver.session.return_value.__aenter__.return_value
        session.run.assert_called_once()


# ── TestEmbeddingResult ──────────────────────────────────────────────────


class TestEmbeddingResult:
    """Tests for the EmbeddingResult dataclass."""

    def test_defaults(self):
        result = EmbeddingResult(
            book_id="b1",
            total_chunks=10,
            embedded=8,
            failed=2,
        )
        assert result.failed_keys == []
        assert result.total_tokens == 0
        assert result.cost_usd == 0.0

    def test_with_failed_keys(self):
        result = EmbeddingResult(
            book_id="b1",
            total_chunks=2,
            embedded=1,
            failed=1,
            failed_keys=[("b1-ch1", 0)],
        )
        assert len(result.failed_keys) == 1
        assert result.failed_keys[0] == ("b1-ch1", 0)
