"""BookIngestionOrchestrator — orchestrates Discovery and Guided ingestion via GraphitiClient."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.saga_profile.pydantic_generator import (
    _UNIVERSAL_TYPES,
    saga_profile_to_graphiti_edges,
    saga_profile_to_graphiti_types,
)

if TYPE_CHECKING:
    from app.core.graphiti_client import GraphitiClient
    from app.services.saga_profile.models import SagaProfile

logger = get_logger(__name__)


class BookIngestionOrchestrator:
    """Orchestrates ingestion of book chapters into Graphiti.

    Supports two modes:
    - **Discovery**: uses only the 6 universal entity types; no prior ontology
      knowledge required.  Suitable for the first book of an unknown saga.
    - **Guided**: merges universal types with induced types and relation types
      derived from a ``SagaProfile``; yields richer, saga-specific extraction.
    """

    def __init__(self, graphiti: GraphitiClient) -> None:
        self.graphiti = graphiti

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ingest_discovery(
        self,
        chapters: list[dict],
        book_id: str,
        book_num: int,
        saga_id: str,
    ) -> None:
        """Discovery Mode: ingest chapters with universal entity types only.

        Args:
            chapters: List of ``{"number": int, "text": str}`` dicts.
            book_id: Identifier of the book being ingested.
            book_num: Ordinal position of the book within the saga.
            saga_id: Identifier of the parent saga.
        """
        entity_types = dict(_UNIVERSAL_TYPES)

        logger.info(
            "ingestion.discovery.start",
            book_id=book_id,
            book_num=book_num,
            saga_id=saga_id,
            chapter_count=len(chapters),
            entity_type_count=len(entity_types),
        )

        for chapter in chapters:
            await self.graphiti.ingest_chapter(
                chapter_text=chapter["text"],
                book_id=book_id,
                book_num=book_num,
                chapter_num=chapter["number"],
                saga_id=saga_id,
                entity_types=entity_types,
            )

        logger.info(
            "ingestion.discovery.complete",
            book_id=book_id,
            saga_id=saga_id,
            chapter_count=len(chapters),
        )

    async def ingest_guided(
        self,
        chapters: list[dict],
        book_id: str,
        book_num: int,
        saga_id: str,
        profile: SagaProfile,
    ) -> None:
        """Guided Mode: ingest chapters with universal + induced types from a SagaProfile.

        Args:
            chapters: List of ``{"number": int, "text": str}`` dicts.
            book_id: Identifier of the book being ingested.
            book_num: Ordinal position of the book within the saga.
            saga_id: Identifier of the parent saga.
            profile: ``SagaProfile`` carrying induced entity and relation types.
        """
        entity_types = saga_profile_to_graphiti_types(profile)
        edge_types, edge_type_map = saga_profile_to_graphiti_edges(profile)

        logger.info(
            "ingestion.guided.start",
            book_id=book_id,
            book_num=book_num,
            saga_id=saga_id,
            chapter_count=len(chapters),
            entity_type_count=len(entity_types),
            edge_type_count=len(edge_types),
        )

        for chapter in chapters:
            await self.graphiti.ingest_chapter(
                chapter_text=chapter["text"],
                book_id=book_id,
                book_num=book_num,
                chapter_num=chapter["number"],
                saga_id=saga_id,
                entity_types=entity_types,
                edge_types=edge_types,
                edge_type_map=edge_type_map,
            )

        logger.info(
            "ingestion.guided.complete",
            book_id=book_id,
            saga_id=saga_id,
            chapter_count=len(chapters),
        )
