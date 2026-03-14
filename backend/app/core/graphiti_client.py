"""GraphitiClient — thin wrapper around graphiti_core.Graphiti.

Initialized once in FastAPI lifespan and injected as a dependency.
Bridges NarrativeTemporalMapper (chapter positions) with Graphiti's
bi-temporal episode model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType

from app.core.logging import get_logger
from app.services.saga_profile.temporal import NarrativeTemporalMapper

logger = get_logger(__name__)


def _build_default_llm_client() -> Any:
    """Build a Graphiti-compatible LLM client from app settings.

    Uses Gemini via OpenAI-compatible API (generativelanguage.googleapis.com).
    Falls back to OpenAI if GEMINI_API_KEY is not set.
    """
    from app.config import settings

    try:
        from graphiti_core.llm_client.config import LLMConfig
        from graphiti_core.llm_client.openai_client import OpenAIClient

        if settings.gemini_api_key:
            config = LLMConfig(
                api_key=settings.gemini_api_key,
                model="gemini-2.5-flash",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                small_model="gemini-2.5-flash",
            )
            logger.info("graphiti_llm_configured", provider="gemini")
            return OpenAIClient(config=config)

        if settings.openai_api_key:
            config = LLMConfig(api_key=settings.openai_api_key, model="gpt-4o-mini")
            logger.info("graphiti_llm_configured", provider="openai")
            return OpenAIClient(config=config)

        logger.warning("graphiti_no_llm_key", detail="Set GEMINI_API_KEY or OPENAI_API_KEY")
        return None
    except Exception:
        logger.warning("graphiti_llm_config_failed", exc_info=True)
        return None


def _build_default_embedder() -> Any:
    """Build a Graphiti-compatible embedder from app settings.

    Uses Gemini embedding via OpenAI-compatible API, or OpenAI if available.
    """
    from app.config import settings

    try:
        from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig

        if settings.gemini_api_key:
            config = OpenAIEmbedderConfig(
                api_key=settings.gemini_api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                embedding_model="text-embedding-004",
                embedding_dim=768,
            )
            logger.info("graphiti_embedder_configured", provider="gemini")
            return OpenAIEmbedder(config=config)

        if settings.openai_api_key:
            config = OpenAIEmbedderConfig(api_key=settings.openai_api_key)
            logger.info("graphiti_embedder_configured", provider="openai")
            return OpenAIEmbedder(config=config)

        logger.warning("graphiti_no_embedder_key")
        return None
    except Exception:
        logger.warning("graphiti_embedder_config_failed", exc_info=True)
        return None


def _build_default_cross_encoder() -> Any:
    """Build a Graphiti-compatible cross-encoder/reranker from app settings."""
    from app.config import settings

    try:
        from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
        from graphiti_core.llm_client.config import LLMConfig

        if settings.gemini_api_key:
            config = LLMConfig(
                api_key=settings.gemini_api_key,
                model="gemini-2.5-flash",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            )
            logger.info("graphiti_cross_encoder_configured", provider="gemini")
            return OpenAIRerankerClient(config=config)

        if settings.openai_api_key:
            config = LLMConfig(api_key=settings.openai_api_key, model="gpt-4o-mini")
            logger.info("graphiti_cross_encoder_configured", provider="openai")
            return OpenAIRerankerClient(config=config)

        logger.warning("graphiti_no_cross_encoder_key")
        return None
    except Exception:
        logger.warning("graphiti_cross_encoder_config_failed", exc_info=True)
        return None


class GraphitiClient:
    """Thin wrapper around :class:`graphiti_core.Graphiti`.

    Encapsulates:
    - Construction with Neo4j credentials + optional LLM/embedder overrides
    - Schema initialisation (indices + constraints)
    - Chapter ingestion mapped to Graphiti episodes
    - Saga-scoped search
    - Graceful shutdown
    """

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_auth: tuple[str, str],
        llm_client: Any | None = None,
        embedder: Any | None = None,
        cross_encoder: Any | None = None,
    ) -> None:
        """Create a Graphiti instance.

        Args:
            neo4j_uri: Bolt URI for the Neo4j instance.
            neo4j_auth: ``(username, password)`` tuple.
            llm_client: Optional LLM client override.
            embedder: Optional embedder override.
            cross_encoder: Optional cross-encoder/reranker override.
        """
        user, password = neo4j_auth

        # Auto-configure from app settings if not provided
        if llm_client is None:
            llm_client = _build_default_llm_client()
        if embedder is None:
            embedder = _build_default_embedder()
        if cross_encoder is None:
            cross_encoder = _build_default_cross_encoder()

        self._client: Graphiti = Graphiti(
            uri=neo4j_uri,
            user=user,
            password=password,
            llm_client=llm_client,
            embedder=embedder,
            cross_encoder=cross_encoder,
        )
        logger.info(
            "graphiti_client_created",
            neo4j_uri=neo4j_uri,
            has_llm_client=llm_client is not None,
            has_embedder=embedder is not None,
        )

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    async def init_schema(self) -> None:
        """Ensure Graphiti indices and constraints exist in Neo4j.

        Should be called once during application startup (FastAPI lifespan).
        """
        logger.info("graphiti_init_schema_start")
        await self._client.build_indices_and_constraints()
        logger.info("graphiti_init_schema_done")

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    async def ingest_chapter(
        self,
        chapter_text: str,
        book_id: str,
        book_num: int,
        chapter_num: int,
        saga_id: str,
        entity_types: dict[str, type] | None = None,
        edge_types: dict[str, type] | None = None,
        edge_type_map: dict[Any, list[str]] | None = None,
    ) -> Any:
        """Ingest a chapter as a Graphiti episode.

        Converts the narrative position ``(book_num, chapter_num)`` to a
        :class:`datetime` via :class:`~app.services.saga_profile.temporal.NarrativeTemporalMapper`
        so that Graphiti can store bi-temporal metadata correctly.

        Args:
            chapter_text: Raw chapter content.
            book_id: Opaque identifier for the book (used as episode name).
            book_num: 1-based book index within the saga.
            chapter_num: 0-based chapter index within the book.
            saga_id: Saga identifier used as Graphiti ``group_id``.
            entity_types: Optional mapping of entity-type names to Pydantic models.
            edge_types: Optional mapping of edge-type names to Pydantic models.
            edge_type_map: Optional mapping from node-type pairs to allowed edge types.

        Returns:
            :class:`graphiti_core.graphiti.AddEpisodeResults` from the underlying call.
        """
        reference_time: datetime = NarrativeTemporalMapper.to_datetime(
            book_num=book_num, chapter_num=chapter_num
        )
        episode_name = f"{book_id}:book{book_num}:ch{chapter_num}"

        logger.info(
            "graphiti_ingest_chapter_start",
            book_id=book_id,
            book_num=book_num,
            chapter_num=chapter_num,
            saga_id=saga_id,
            reference_time=reference_time.isoformat(),
        )

        result = await self._client.add_episode(
            name=episode_name,
            episode_body=chapter_text,
            source_description=f"Book {book_num}, Chapter {chapter_num} of {saga_id}",
            reference_time=reference_time,
            source=EpisodeType.text,
            group_id=saga_id,
            entity_types=entity_types,
            edge_types=edge_types,
            edge_type_map=edge_type_map,
        )

        logger.info(
            "graphiti_ingest_chapter_done",
            book_id=book_id,
            book_num=book_num,
            chapter_num=chapter_num,
        )
        return result

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        saga_id: str,
        num_results: int = 20,
    ) -> list[Any]:
        """Search the knowledge graph within a saga's scope.

        Args:
            query: Natural-language search query.
            saga_id: Limits results to this saga's group.
            num_results: Maximum number of edges to return (default 20).

        Returns:
            List of :class:`graphiti_core.edges.EntityEdge` objects.
        """
        logger.info(
            "graphiti_search_start",
            saga_id=saga_id,
            num_results=num_results,
        )
        results = await self._client.search(
            query=query,
            group_ids=[saga_id],
            num_results=num_results,
        )
        logger.info("graphiti_search_done", result_count=len(results))
        return results

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying Graphiti connection pool."""
        logger.info("graphiti_client_closing")
        await self._client.close()
        logger.info("graphiti_client_closed")
