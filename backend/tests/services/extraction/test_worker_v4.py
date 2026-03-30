"""Tests for process_book_extraction_v4 arq worker function.

Covers: happy path, DLQ push on chapter failure, quota exhausted early exit,
cost ceiling break, auto-chain to embeddings, and non-content chapter filtering.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import CostCeilingError, QuotaExhaustedError
from app.schemas.book import ChapterData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chapter(number: int, title: str = "") -> ChapterData:
    """Build a minimal ChapterData for testing."""
    return ChapterData(
        number=number,
        title=title or f"Chapter {number}",
        text=f"Chapter {number} text with enough words to pass.",
    )


def _make_ctx() -> dict:
    """Build a minimal arq ctx dict with mocked dependencies."""
    redis_mock = AsyncMock()
    redis_mock.enqueue_job = AsyncMock()

    dlq_mock = AsyncMock()
    dlq_mock.push_failure = AsyncMock()

    return {
        "neo4j_driver": MagicMock(),
        "redis": redis_mock,
        "dlq": dlq_mock,
        "cost_tracker": None,
    }


def _make_book_repo_mock(chapters: list[ChapterData]) -> AsyncMock:
    """Build an AsyncMock BookRepository with sensible defaults."""
    repo = AsyncMock()
    repo.get_book = AsyncMock(return_value={"id": "book-1", "title": "Test Book"})
    repo.get_chapters_for_extraction = AsyncMock(return_value=chapters)
    repo.get_chapter_regex_json = AsyncMock(return_value={})
    repo.reset_extraction = AsyncMock(return_value=0)
    repo.update_book_status = AsyncMock()
    repo.update_chapter_status = AsyncMock()
    repo.update_book_chapters_processed = AsyncMock()
    repo.save_entity_registry = AsyncMock()
    repo.get_series_book_ids = AsyncMock(return_value=[])
    repo.load_entity_registry = AsyncMock(return_value=None)
    return repo


def _make_entity_repo_mock() -> AsyncMock:
    """Build an AsyncMock EntityRepository."""
    repo = AsyncMock()
    repo.upsert_v4_entities = AsyncMock(return_value={"character": 1})
    return repo


# ---------------------------------------------------------------------------
# Shared patch targets (all resolved relative to where they are used in tasks.py)
# ---------------------------------------------------------------------------

BOOK_REPO_PATH = "app.workers.tasks.BookRepository"
ENTITY_REPO_PATH = "app.repositories.entity_repo.EntityRepository"

# Lazy-imported inside process_book_extraction_v4
EXTRACT_CHAPTER_V4_PATH = "app.services.extraction.extract_chapter_v4"
IS_NON_CONTENT_PATH = "app.services.graph_builder._is_non_content_chapter"
STREAMING_DEDUP_PATH = "app.services.deduplication.streaming_chapter_dedup"
ITERATIVE_CLUSTER_PATH = "app.services.extraction.book_level.iterative_cluster"
ENTITY_SUMMARIES_PATH = "app.services.extraction.book_level.generate_entity_summaries"
STATE_SNAPSHOTS_PATH = "app.services.extraction.book_level.generate_state_snapshots"
COMMUNITY_CLUSTER_PATH = "app.services.extraction.book_level.community_cluster"
ONTOLOGY_LOADER_PATH = "app.core.ontology_loader.OntologyLoader.from_layers"
ONTOLOGY_INDUCER_PATH = "app.services.extraction.ontology_inducer.induce_ontology"
LOCAL_EMBEDDER_PATH = "app.llm.embeddings.LocalEmbedder"
ENTITY_REGISTRY_PATH = "app.services.extraction.entity_registry.EntityRegistry"
COST_CEILING_IMPORT = "app.core.exceptions.CostCeilingError"

BOOK_ID = "book-1"


def _mock_extract_result(entities: int = 1) -> dict:
    """Minimal result dict returned by extract_chapter_v4."""
    return {
        "entities": [{"name": f"Entity{i}", "type": "Character"} for i in range(entities)],
        "relations": [],
        "ended_relations": [],
        "entity_registry": None,
    }


def _mock_ontology():
    """Return a minimal ontology mock."""
    ont = MagicMock()
    ont.layers_loaded = ["core"]
    ont.node_types = ["Character"]
    ont.relationship_types = ["INTERACTS_WITH"]
    ont.extend_with_induced = MagicMock()
    return ont


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def chapters_2() -> list[ChapterData]:
    return [_make_chapter(1), _make_chapter(2)]


@pytest.fixture
def ctx() -> dict:
    return _make_ctx()


# ---------------------------------------------------------------------------
# TestWorkerV4HappyPath
# ---------------------------------------------------------------------------

class TestWorkerV4HappyPath:
    """Happy-path scenarios for process_book_extraction_v4."""

    @pytest.mark.asyncio
    async def test_processes_all_chapters(self, ctx, chapters_2):
        """Two chapters → status 'extracted', chapters_processed=2, chapters_failed=0."""
        from app.workers.tasks import process_book_extraction_v4

        book_repo = _make_book_repo_mock(chapters_2)
        entity_repo = _make_entity_repo_mock()

        with (
            patch(BOOK_REPO_PATH, return_value=book_repo),
            patch("app.repositories.entity_repo.EntityRepository", return_value=entity_repo),
            patch(IS_NON_CONTENT_PATH, return_value=False),
            patch(EXTRACT_CHAPTER_V4_PATH, new=AsyncMock(return_value=_mock_extract_result())),
            patch(STREAMING_DEDUP_PATH, new=AsyncMock(return_value={})),
            patch(ONTOLOGY_LOADER_PATH, return_value=_mock_ontology()),
            patch(ONTOLOGY_INDUCER_PATH, new=AsyncMock(return_value={})),
            patch(ITERATIVE_CLUSTER_PATH, new=AsyncMock(return_value={})),
            patch(ENTITY_SUMMARIES_PATH, new=AsyncMock(return_value=[])),
            patch(STATE_SNAPSHOTS_PATH, new=AsyncMock(return_value=0)),
            patch(COMMUNITY_CLUSTER_PATH, new=AsyncMock(return_value=[])),
            patch(LOCAL_EMBEDDER_PATH, return_value=MagicMock()),
        ):
            result = await process_book_extraction_v4(
                ctx=ctx,
                book_id=BOOK_ID,
                genre="litrpg",
            )

        assert result["status"] == "extracted"
        assert result["chapters_processed"] == 2
        assert result["chapters_failed"] == 0
        assert result["pipeline"] == "v4"

    @pytest.mark.asyncio
    async def test_auto_enqueues_embeddings(self, ctx, chapters_2):
        """After extraction, ctx['redis'].enqueue_job('process_book_embeddings', ...) is called."""
        from app.workers.tasks import process_book_extraction_v4

        book_repo = _make_book_repo_mock(chapters_2)
        entity_repo = _make_entity_repo_mock()

        with (
            patch(BOOK_REPO_PATH, return_value=book_repo),
            patch("app.repositories.entity_repo.EntityRepository", return_value=entity_repo),
            patch(IS_NON_CONTENT_PATH, return_value=False),
            patch(EXTRACT_CHAPTER_V4_PATH, new=AsyncMock(return_value=_mock_extract_result())),
            patch(STREAMING_DEDUP_PATH, new=AsyncMock(return_value={})),
            patch(ONTOLOGY_LOADER_PATH, return_value=_mock_ontology()),
            patch(ONTOLOGY_INDUCER_PATH, new=AsyncMock(return_value={})),
            patch(ITERATIVE_CLUSTER_PATH, new=AsyncMock(return_value={})),
            patch(ENTITY_SUMMARIES_PATH, new=AsyncMock(return_value=[])),
            patch(STATE_SNAPSHOTS_PATH, new=AsyncMock(return_value=0)),
            patch(COMMUNITY_CLUSTER_PATH, new=AsyncMock(return_value=[])),
            patch(LOCAL_EMBEDDER_PATH, return_value=MagicMock()),
        ):
            await process_book_extraction_v4(ctx=ctx, book_id=BOOK_ID)

        ctx["redis"].enqueue_job.assert_awaited_once()
        call_args = ctx["redis"].enqueue_job.call_args
        assert call_args.args[0] == "process_book_embeddings"
        assert call_args.args[1] == BOOK_ID


# ---------------------------------------------------------------------------
# TestWorkerV4ErrorHandling
# ---------------------------------------------------------------------------

class TestWorkerV4ErrorHandling:
    """Error-handling scenarios for process_book_extraction_v4."""

    @pytest.mark.asyncio
    async def test_chapter_failure_pushes_to_dlq(self, ctx, chapters_2):
        """Chapter 1 raises RuntimeError → DLQ.push_failure called, chapter 2 still processed, status 'partial'."""
        from app.workers.tasks import process_book_extraction_v4

        book_repo = _make_book_repo_mock(chapters_2)
        entity_repo = _make_entity_repo_mock()

        call_count = 0

        async def extract_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("LLM timeout on chapter 1")
            return _mock_extract_result()

        with (
            patch(BOOK_REPO_PATH, return_value=book_repo),
            patch("app.repositories.entity_repo.EntityRepository", return_value=entity_repo),
            patch(IS_NON_CONTENT_PATH, return_value=False),
            patch(EXTRACT_CHAPTER_V4_PATH, new=AsyncMock(side_effect=extract_side_effect)),
            patch(STREAMING_DEDUP_PATH, new=AsyncMock(return_value={})),
            patch(ONTOLOGY_LOADER_PATH, return_value=_mock_ontology()),
            patch(ONTOLOGY_INDUCER_PATH, new=AsyncMock(return_value={})),
            patch(ITERATIVE_CLUSTER_PATH, new=AsyncMock(return_value={})),
            patch(ENTITY_SUMMARIES_PATH, new=AsyncMock(return_value=[])),
            patch(STATE_SNAPSHOTS_PATH, new=AsyncMock(return_value=0)),
            patch(COMMUNITY_CLUSTER_PATH, new=AsyncMock(return_value=[])),
            patch(LOCAL_EMBEDDER_PATH, return_value=MagicMock()),
        ):
            result = await process_book_extraction_v4(ctx=ctx, book_id=BOOK_ID)

        # DLQ should have received the failure for chapter 1
        ctx["dlq"].push_failure.assert_awaited_once()
        dlq_call = ctx["dlq"].push_failure.call_args
        assert dlq_call.kwargs["book_id"] == BOOK_ID
        assert dlq_call.kwargs["chapter"] == 1

        # Status should be partial (one failed, one succeeded)
        assert result["status"] == "partial"
        assert result["chapters_failed"] == 1
        assert result["chapters_processed"] == 1  # chapter 2 succeeded

    @pytest.mark.asyncio
    async def test_quota_exhausted_stops_immediately(self, ctx, chapters_2):
        """QuotaExhaustedError on chapter 1 → stops immediately, returns stopped_reason='quota_exhausted'."""
        from app.workers.tasks import process_book_extraction_v4

        book_repo = _make_book_repo_mock(chapters_2)
        entity_repo = _make_entity_repo_mock()

        async def extract_quota_error(**kwargs):
            raise QuotaExhaustedError(provider="gemini", message="Quota hit")

        with (
            patch(BOOK_REPO_PATH, return_value=book_repo),
            patch("app.repositories.entity_repo.EntityRepository", return_value=entity_repo),
            patch(IS_NON_CONTENT_PATH, return_value=False),
            patch(EXTRACT_CHAPTER_V4_PATH, new=AsyncMock(side_effect=extract_quota_error)),
            patch(STREAMING_DEDUP_PATH, new=AsyncMock(return_value={})),
            patch(ONTOLOGY_LOADER_PATH, return_value=_mock_ontology()),
            patch(ONTOLOGY_INDUCER_PATH, new=AsyncMock(return_value={})),
            patch(ITERATIVE_CLUSTER_PATH, new=AsyncMock(return_value={})),
            patch(ENTITY_SUMMARIES_PATH, new=AsyncMock(return_value=[])),
            patch(STATE_SNAPSHOTS_PATH, new=AsyncMock(return_value=0)),
            patch(COMMUNITY_CLUSTER_PATH, new=AsyncMock(return_value=[])),
            patch(LOCAL_EMBEDDER_PATH, return_value=MagicMock()),
        ):
            result = await process_book_extraction_v4(ctx=ctx, book_id=BOOK_ID)

        assert result["stopped_reason"] == "quota_exhausted"
        assert result["stopped_at_chapter"] == 1
        assert result["provider"] == "gemini"
        # Only 0 chapters processed (stopped at first)
        assert result["chapters_processed"] == 0

    @pytest.mark.asyncio
    async def test_cost_ceiling_breaks_loop(self, ctx, chapters_2):
        """CostCeilingError on chapter 2 → loop breaks, cost_ceiling_hit=True in result."""
        from app.workers.tasks import process_book_extraction_v4

        book_repo = _make_book_repo_mock(chapters_2)
        entity_repo = _make_entity_repo_mock()

        call_count = 0

        async def extract_with_ceiling(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise CostCeilingError("Cost ceiling exceeded")
            return _mock_extract_result()

        with (
            patch(BOOK_REPO_PATH, return_value=book_repo),
            patch("app.repositories.entity_repo.EntityRepository", return_value=entity_repo),
            patch(IS_NON_CONTENT_PATH, return_value=False),
            patch(EXTRACT_CHAPTER_V4_PATH, new=AsyncMock(side_effect=extract_with_ceiling)),
            patch(STREAMING_DEDUP_PATH, new=AsyncMock(return_value={})),
            patch(ONTOLOGY_LOADER_PATH, return_value=_mock_ontology()),
            patch(ONTOLOGY_INDUCER_PATH, new=AsyncMock(return_value={})),
            patch(ITERATIVE_CLUSTER_PATH, new=AsyncMock(return_value={})),
            patch(ENTITY_SUMMARIES_PATH, new=AsyncMock(return_value=[])),
            patch(STATE_SNAPSHOTS_PATH, new=AsyncMock(return_value=0)),
            patch(COMMUNITY_CLUSTER_PATH, new=AsyncMock(return_value=[])),
            patch(LOCAL_EMBEDDER_PATH, return_value=MagicMock()),
        ):
            result = await process_book_extraction_v4(ctx=ctx, book_id=BOOK_ID)

        assert result["cost_ceiling_hit"] is True
        assert result["status"] == "cost_ceiling_hit"
        # Chapter 1 succeeded, chapter 2 hit ceiling
        assert result["chapters_processed"] == 1


# ---------------------------------------------------------------------------
# TestWorkerV4ChapterFiltering
# ---------------------------------------------------------------------------

class TestWorkerV4ChapterFiltering:
    """Non-content chapter filtering in process_book_extraction_v4."""

    @pytest.mark.asyncio
    async def test_non_content_chapters_skipped(self, ctx, chapters_2):
        """_is_non_content_chapter skips chapter 1 → only chapter 2 is processed."""
        from app.workers.tasks import process_book_extraction_v4

        book_repo = _make_book_repo_mock(chapters_2)
        entity_repo = _make_entity_repo_mock()

        def is_non_content(chapter: ChapterData) -> bool:
            # Skip chapter 1 only
            return chapter.number == 1

        with (
            patch(BOOK_REPO_PATH, return_value=book_repo),
            patch("app.repositories.entity_repo.EntityRepository", return_value=entity_repo),
            patch(IS_NON_CONTENT_PATH, side_effect=is_non_content),
            patch(EXTRACT_CHAPTER_V4_PATH, new=AsyncMock(return_value=_mock_extract_result())),
            patch(STREAMING_DEDUP_PATH, new=AsyncMock(return_value={})),
            patch(ONTOLOGY_LOADER_PATH, return_value=_mock_ontology()),
            patch(ONTOLOGY_INDUCER_PATH, new=AsyncMock(return_value={})),
            patch(ITERATIVE_CLUSTER_PATH, new=AsyncMock(return_value={})),
            patch(ENTITY_SUMMARIES_PATH, new=AsyncMock(return_value=[])),
            patch(STATE_SNAPSHOTS_PATH, new=AsyncMock(return_value=0)),
            patch(COMMUNITY_CLUSTER_PATH, new=AsyncMock(return_value=[])),
            patch(LOCAL_EMBEDDER_PATH, return_value=MagicMock()),
        ):
            result = await process_book_extraction_v4(ctx=ctx, book_id=BOOK_ID)

        # Only chapter 2 was processed
        assert result["chapters_processed"] == 1
        assert result["status"] == "extracted"

        # extract_chapter_v4 called exactly once (for chapter 2 only)
        from app.services.extraction import extract_chapter_v4  # noqa: F401 (just for the mock)
        # Verify via chapters_processed count — chapter 1 was skipped
        assert result["chapters_failed"] == 0
