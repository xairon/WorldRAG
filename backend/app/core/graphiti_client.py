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
    ) -> None:
        """Create a Graphiti instance.

        Args:
            neo4j_uri: Bolt URI for the Neo4j instance (e.g. ``bolt://localhost:7687``).
            neo4j_auth: ``(username, password)`` tuple.
            llm_client: Optional :class:`graphiti_core.llm_client.client.LLMClient`
                override. If *None* Graphiti uses its default client.
            embedder: Optional :class:`graphiti_core.embedder.client.EmbedderClient`
                override. If *None* Graphiti uses its default embedder.
        """
        user, password = neo4j_auth
        self._client: Graphiti = Graphiti(
            uri=neo4j_uri,
            user=user,
            password=password,
            llm_client=llm_client,
            embedder=embedder,
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
