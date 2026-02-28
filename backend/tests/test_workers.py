"""Tests for arq worker settings and task functions.

All tests use mocked infrastructure (no real Neo4j/Redis).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.settings import _parse_redis_settings
from app.workers.tasks import ARQ_QUEUE, process_book_embeddings, process_book_extraction

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_ctx():
    """Create a mock arq context dict with all required resources."""
    driver = AsyncMock()
    dlq = MagicMock()
    dlq.push_failure = AsyncMock()
    arq_redis = AsyncMock()
    arq_redis.enqueue_job = AsyncMock()
    cost_tracker = MagicMock()
    cost_tracker.record = AsyncMock()

    return {
        "neo4j_driver": driver,
        "dlq": dlq,
        "redis": arq_redis,  # arq's ArqRedis pool
        "cost_tracker": cost_tracker,
    }


# ── TestParseRedisSettings ────────────────────────────────────────────────


class TestParseRedisSettings:
    """Tests for _parse_redis_settings()."""

    def test_default_url(self):
        """Parses the default redis URL from settings."""
        rs = _parse_redis_settings()
        assert rs.host in ("localhost", "127.0.0.1")
        assert rs.port == 6379
        assert rs.password == "worldrag"

    def test_custom_url(self, monkeypatch):
        """Parses a custom redis URL."""
        monkeypatch.setattr(
            "app.workers.settings.settings",
            MagicMock(redis_url="redis://:secret@myhost:6380/2"),
        )
        rs = _parse_redis_settings()
        assert rs.host == "myhost"
        assert rs.port == 6380
        assert rs.password == "secret"


# ── TestWorkerSettings ────────────────────────────────────────────────────


class TestWorkerSettings:
    """Tests for the WorkerSettings class configuration."""

    def test_has_required_functions(self):
        from app.workers.settings import WorkerSettings

        func_names = [f.__name__ for f in WorkerSettings.functions]
        assert "process_book_extraction" in func_names
        assert "process_book_embeddings" in func_names

    def test_queue_name(self):
        from app.workers.settings import WorkerSettings

        assert WorkerSettings.queue_name == "worldrag:arq"


# ── TestProcessBookExtraction ─────────────────────────────────────────────


class TestProcessBookExtraction:
    """Tests for the process_book_extraction task."""

    async def test_raises_on_missing_book(self, mock_ctx):
        with (
            patch("app.workers.tasks.BookRepository") as mock_repo_cls,
        ):
            instance = mock_repo_cls.return_value
            instance.get_book = AsyncMock(return_value=None)

            with pytest.raises(ValueError, match="not found"):
                await process_book_extraction(mock_ctx, "nonexistent")

    async def test_raises_on_no_chapters(self, mock_ctx):
        with (
            patch("app.workers.tasks.BookRepository") as mock_repo_cls,
        ):
            instance = mock_repo_cls.return_value
            instance.get_book = AsyncMock(return_value={"id": "b1", "status": "completed"})
            instance.get_chapters_for_extraction = AsyncMock(return_value=[])

            with pytest.raises(ValueError, match="No chapters"):
                await process_book_extraction(mock_ctx, "b1")

    async def test_calls_build_book_graph_and_enqueues_embeddings(self, mock_ctx):
        fake_result = {
            "chapters_processed": 3,
            "chapters_failed": 0,
            "failed_chapters": [],
            "total_entities": 42,
            "status": "extracted",
        }

        from app.config import settings

        with (
            patch("app.workers.tasks.BookRepository") as mock_repo_cls,
            patch(
                "app.services.graph_builder.build_book_graph",
                new_callable=AsyncMock,
                return_value=fake_result,
            ) as mock_build,
            patch.object(settings, "use_v3_pipeline", False),
        ):
            instance = mock_repo_cls.return_value
            instance.get_book = AsyncMock(
                return_value={"id": "b1", "status": "completed", "genre": "litrpg"},
            )
            instance.get_chapters_for_extraction = AsyncMock(
                return_value=[MagicMock(number=1)],
            )
            instance.get_chapter_regex_json = AsyncMock(return_value={})

            result = await process_book_extraction(mock_ctx, "b1", "litrpg", "")

        # Verify build_book_graph was called
        mock_build.assert_called_once()
        call_kwargs = mock_build.call_args.kwargs
        assert call_kwargs["book_id"] == "b1"
        assert call_kwargs["dlq"] is mock_ctx["dlq"]

        # Verify embedding job was enqueued
        mock_ctx["redis"].enqueue_job.assert_called_once_with(
            "process_book_embeddings",
            "b1",
            _queue_name=ARQ_QUEUE,
            _job_id="embed:b1",
        )

        assert result["chapters_processed"] == 3
        assert result["total_entities"] == 42

    async def test_v3_delegation_when_enabled(self, mock_ctx):
        """When use_v3_pipeline=True, process_book_extraction delegates to V3."""
        from app.config import settings

        with (
            patch(
                "app.workers.tasks.process_book_extraction_v3",
                new_callable=AsyncMock,
                return_value={"pipeline": "v3", "chapters_processed": 2},
            ) as mock_v3,
            patch.object(settings, "use_v3_pipeline", True),
            patch.object(settings, "extraction_language", "fr"),
        ):
            result = await process_book_extraction(
                mock_ctx,
                "b1",
                "litrpg",
                "test-series",
            )

        mock_v3.assert_called_once_with(
            mock_ctx,
            "b1",
            "litrpg",
            "test-series",
            None,
            "fr",
        )
        assert result["pipeline"] == "v3"


# ── TestProcessBookEmbeddings ─────────────────────────────────────────────


class TestProcessBookEmbeddings:
    """Tests for the process_book_embeddings task."""

    async def test_no_chunks_returns_zero(self, mock_ctx):
        with (
            patch("app.workers.tasks.BookRepository") as mock_repo_cls,
        ):
            instance = mock_repo_cls.return_value
            instance.get_chunks_for_embedding = AsyncMock(return_value=[])

            result = await process_book_embeddings(mock_ctx, "b1")

        assert result["embedded"] == 0
        assert result["failed"] == 0

    async def test_calls_embedding_pipeline(self, mock_ctx):
        from app.services.embedding_pipeline import EmbeddingResult

        chunks = [{"chapter_id": "b1-ch1", "position": 0, "text": "test"}]
        fake_emb_result = EmbeddingResult(
            book_id="b1",
            total_chunks=1,
            embedded=1,
            failed=0,
            total_tokens=100,
            cost_usd=0.000006,
        )

        with (
            patch("app.workers.tasks.BookRepository") as mock_repo_cls,
            patch(
                "app.services.embedding_pipeline.embed_book_chunks",
                new_callable=AsyncMock,
                return_value=fake_emb_result,
            ) as mock_embed,
        ):
            instance = mock_repo_cls.return_value
            instance.get_chunks_for_embedding = AsyncMock(return_value=chunks)
            instance.update_book_status = AsyncMock()

            result = await process_book_embeddings(mock_ctx, "b1")

        mock_embed.assert_called_once()
        assert result["embedded"] == 1
        assert result["cost_usd"] == 0.000006
        # Status should be updated to "embedded"
        instance.update_book_status.assert_any_call("b1", "embedded")
