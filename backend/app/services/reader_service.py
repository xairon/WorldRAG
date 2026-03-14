"""Reader agent service — chapter-scoped Q&A."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from neo4j import AsyncDriver

from langchain_core.messages import HumanMessage

from app.agents.reader.graph import build_reader_graph
from app.core.logging import get_logger
from app.repositories.base import Neo4jRepository

logger = get_logger(__name__)


class ReaderService:
    """Chapter-scoped Q&A service using the Reader LangGraph agent."""

    _compiled_graph: Any = None
    _shared_repo: Any = None
    _shared_driver: Any = None

    def __init__(self, driver: AsyncDriver, checkpointer: Any = None) -> None:
        self.repo = Neo4jRepository(driver)

        if ReaderService._shared_driver is not None and ReaderService._shared_driver is not driver:
            logger.info("reader_service_driver_changed_recompiling")
            ReaderService._compiled_graph = None
            ReaderService._shared_repo = None

        if ReaderService._compiled_graph is None:
            ReaderService._shared_repo = self.repo
            ReaderService._shared_driver = driver
            builder = build_reader_graph(repo=self.repo)
            ReaderService._compiled_graph = builder.compile(checkpointer=checkpointer)

        self._graph = ReaderService._compiled_graph

    async def query(
        self,
        query: str,
        book_id: str,
        chapter_number: int,
        *,
        max_chapter: int | None = None,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """Run the reader agent for a chapter-scoped question."""
        state_input: dict[str, Any] = {
            "messages": [HumanMessage(content=query)],
            "query": query,
            "book_id": book_id,
            "chapter_number": chapter_number,
            "max_chapter": max_chapter or chapter_number,
        }

        config: dict[str, Any] = {}
        if thread_id:
            config["configurable"] = {"thread_id": thread_id}

        result = await self._graph.ainvoke(state_input, config=config)

        return {
            "answer": result.get("generation", ""),
            "route": result.get("route", "context_qa"),
            "paragraphs_used": len(result.get("paragraph_context", [])),
            "entities_found": len(result.get("entity_annotations", [])),
        }
