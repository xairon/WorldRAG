"""Chat/RAG query service.

Implements the hybrid retrieval pipeline for answering user questions
about novels grounded in the Knowledge Graph:

    Vector search (local embeddings) → Rerank (Cohere, optional) → Graph context → LLM generate
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from app.config import settings
from app.core.logging import get_logger
from app.core.resilience import retry_llm_call
from app.llm.embeddings import LocalEmbedder
from app.llm.providers import get_langchain_llm
from app.repositories.base import Neo4jRepository
from app.schemas.chat import (
    ChatResponse,
    RelatedEntity,
    SourceChunk,
)

if TYPE_CHECKING:
    from neo4j import AsyncDriver

logger = get_logger(__name__)

# System prompt grounding the LLM on the retrieved context
_SYSTEM_PROMPT = """\
You are WorldRAG, an expert assistant for fiction novel universes.
Answer the user's question using ONLY the provided context from the KG and source chunks.
If the context doesn't contain enough information, say so honestly.

Rules:
- Ground every claim in the provided sources.
- Reference chapters when possible (e.g., "In Chapter 5, ...").
- Keep answers concise but thorough.
- If asked about character progression (levels, skills, classes), be precise with numbers.
- Never invent information not present in the context.
"""


class ChatService:
    """Hybrid retrieval + generation service for novel Q&A."""

    def __init__(self, driver: AsyncDriver) -> None:
        self.repo = Neo4jRepository(driver)
        self.embedder = LocalEmbedder()
        self._reranker = None

    @property
    def reranker(self):
        """Lazy-load reranker only if Cohere API key is configured."""
        if self._reranker is None and settings.cohere_api_key:
            from app.llm.reranker import CohereReranker

            self._reranker = CohereReranker()
        return self._reranker

    async def query(
        self,
        query: str,
        book_id: str,
        *,
        top_k: int = 20,
        rerank_top_n: int = 5,
        min_relevance: float = 0.1,
        include_sources: bool = True,
        max_chapter: int | None = None,
    ) -> ChatResponse:
        """Run the full RAG pipeline.

        1. Embed query with local model
        2. Vector search on Chunk embeddings (Neo4j vector index)
        3. Rerank with Cohere (if available) or use vector scores
        4. Fetch related KG entities from matching chunks
        5. Generate answer with LLM

        Args:
            query: User question.
            book_id: Book to scope the search to.
            top_k: Number of chunks to retrieve from vector search.
            rerank_top_n: Number of chunks to keep after reranking.
            min_relevance: Minimum reranker relevance score.
            include_sources: Whether to include source chunks in response.

        Returns:
            ChatResponse with answer, sources, and related entities.
        """
        # Step 1: Embed the query
        query_embedding = await self.embedder.embed_query(query)

        # Step 2: Vector search on chunks
        chunks = await self._vector_search(query_embedding, book_id, top_k, max_chapter=max_chapter)

        if not chunks:
            return ChatResponse(
                answer="I couldn't find any relevant content in this book for your question. "
                "Make sure the book has been fully processed (extracted and embedded).",
                chunks_retrieved=0,
                chunks_after_rerank=0,
            )

        # Step 3: Rerank or just take top-N by vector score
        if self.reranker:
            chunk_texts = [c["text"] for c in chunks]
            reranked = await self.reranker.rerank(
                query=query,
                documents=chunk_texts,
                top_n=rerank_top_n,
                min_relevance=min_relevance,
            )

            if not reranked:
                return ChatResponse(
                    answer=(
                        "I found some content but it doesn't seem"
                        " relevant enough to your question. "
                        "Try rephrasing or asking something more"
                        " specific about the story."
                    ),
                    chunks_retrieved=len(chunks),
                    chunks_after_rerank=0,
                )

            top_chunks = [chunks[r.index] for r in reranked]
            relevance_scores = [r.relevance_score for r in reranked]
        else:
            # No reranker — use top-N from vector search (already sorted by score)
            top_chunks = chunks[:rerank_top_n]
            relevance_scores = [c.get("score", 0.0) for c in top_chunks]

        # Step 4: Fetch related KG entities
        chapter_numbers = list({c["chapter_number"] for c in top_chunks})
        related_entities = await self._fetch_related_entities(
            book_id, chapter_numbers, max_chapter=max_chapter
        )

        # Step 5: Generate answer
        context = self._build_context(top_chunks, relevance_scores, related_entities)
        answer = await self._generate_answer(query, context)

        # Build response
        sources: list[SourceChunk] = []
        if include_sources:
            sources = [
                SourceChunk(
                    text=chunk["text"][:500],
                    chapter_number=chunk["chapter_number"],
                    chapter_title=chunk.get("chapter_title", ""),
                    position=chunk.get("position", 0),
                    relevance_score=score,
                )
                for chunk, score in zip(top_chunks, relevance_scores, strict=True)
            ]

        logger.info(
            "chat_query_completed",
            book_id=book_id,
            query_len=len(query),
            chunks_retrieved=len(chunks),
            chunks_after_rerank=len(top_chunks),
            entities_found=len(related_entities),
        )

        return ChatResponse(
            answer=answer,
            sources=sources,
            related_entities=related_entities,
            chunks_retrieved=len(chunks),
            chunks_after_rerank=len(top_chunks),
        )

    async def query_stream(
        self,
        query: str,
        book_id: str,
        *,
        top_k: int = 20,
        rerank_top_n: int = 5,
        min_relevance: float = 0.1,
        max_chapter: int | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream the RAG pipeline as SSE events.

        Yields dicts with "event" and "data" keys:
          - {"event": "sources", "data": {sources, related_entities,
            chunks_retrieved, chunks_after_rerank}}
          - {"event": "token", "data": {"token": "..."}}
          - {"event": "done", "data": {}}
          - {"event": "error", "data": {"message": "..."}}
        """
        import json

        from langchain_core.messages import HumanMessage, SystemMessage

        # Step 1-3: Retrieve and rerank (same as query)
        query_embedding = await self.embedder.embed_query(query)
        chunks = await self._vector_search(query_embedding, book_id, top_k, max_chapter=max_chapter)

        if not chunks:
            yield {"event": "error", "data": json.dumps({"message": "No relevant content found."})}
            return

        if self.reranker:
            chunk_texts = [c["text"] for c in chunks]
            reranked = await self.reranker.rerank(
                query=query,
                documents=chunk_texts,
                top_n=rerank_top_n,
                min_relevance=min_relevance,
            )
            if not reranked:
                yield {
                    "event": "error",
                    "data": json.dumps({"message": "Content not relevant enough."}),
                }
                return
            top_chunks = [chunks[r.index] for r in reranked]
            relevance_scores = [r.relevance_score for r in reranked]
        else:
            top_chunks = chunks[:rerank_top_n]
            relevance_scores = [c.get("score", 0.0) for c in top_chunks]

        # Step 4: Fetch related entities
        chapter_numbers = list({c["chapter_number"] for c in top_chunks})
        related_entities = await self._fetch_related_entities(
            book_id, chapter_numbers, max_chapter=max_chapter
        )

        # Emit sources event before streaming tokens
        sources = [
            SourceChunk(
                text=chunk["text"][:500],
                chapter_number=chunk["chapter_number"],
                chapter_title=chunk.get("chapter_title", ""),
                position=chunk.get("position", 0),
                relevance_score=score,
            )
            for chunk, score in zip(top_chunks, relevance_scores, strict=True)
        ]
        yield {
            "event": "sources",
            "data": json.dumps(
                {
                    "sources": [s.model_dump() for s in sources],
                    "related_entities": [e.model_dump() for e in related_entities],
                    "chunks_retrieved": len(chunks),
                    "chunks_after_rerank": len(top_chunks),
                }
            ),
        }

        # Step 5: Stream LLM answer
        context = self._build_context(top_chunks, relevance_scores, related_entities)
        llm = get_langchain_llm(settings.llm_chat)
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=f"{context}\n\n---\n\nQuestion: {query}"),
        ]

        try:
            async for chunk in llm.astream(messages):
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                if token:
                    yield {"event": "token", "data": json.dumps({"token": token})}
        except Exception:
            logger.exception("chat_stream_llm_error")
            yield {"event": "error", "data": json.dumps({"message": "LLM generation failed."})}
            return

        yield {"event": "done", "data": "{}"}

        logger.info(
            "chat_stream_completed",
            book_id=book_id,
            query_len=len(query),
            chunks_retrieved=len(chunks),
            chunks_after_rerank=len(top_chunks),
        )

    async def _vector_search(
        self,
        query_embedding: list[float],
        book_id: str,
        top_k: int,
        *,
        max_chapter: int | None = None,
    ) -> list[dict[str, Any]]:
        """Search chunks by vector similarity using the Neo4j vector index."""
        results = await self.repo.execute_read(
            """
            CALL db.index.vector.queryNodes('chunk_embedding', $top_k, $embedding)
            YIELD node AS chunk, score
            MATCH (chap:Chapter)-[:HAS_CHUNK]->(chunk)
            WHERE chap.book_id = $book_id
              AND ($max_chapter IS NULL OR chap.number <= $max_chapter)
            RETURN chunk.text AS text,
                   chap.number AS chapter_number,
                   chap.title AS chapter_title,
                   chunk.position AS position,
                   score
            ORDER BY score DESC
            """,
            {
                "embedding": query_embedding,
                "book_id": book_id,
                "top_k": top_k,
                "max_chapter": max_chapter,
            },
        )
        return results

    async def _fetch_related_entities(
        self,
        book_id: str,
        chapter_numbers: list[int],
        *,
        max_chapter: int | None = None,
    ) -> list[RelatedEntity]:
        """Fetch KG entities grounded in the relevant chapters."""
        if not chapter_numbers:
            return []

        results = await self.repo.execute_read(
            """
            MATCH (entity)-[:GROUNDED_IN|MENTIONED_IN]->(chap:Chapter)
            WHERE chap.book_id = $book_id AND chap.number IN $chapters
              AND NOT entity:Chunk AND NOT entity:Book AND NOT entity:Chapter
              AND ($max_chapter IS NULL OR chap.number <= $max_chapter)
            RETURN DISTINCT entity.name AS name,
                   labels(entity)[0] AS label,
                   entity.description AS description
            ORDER BY label, name
            LIMIT 30
            """,
            {"book_id": book_id, "chapters": chapter_numbers, "max_chapter": max_chapter},
        )

        return [
            RelatedEntity(
                name=r["name"],
                label=r["label"],
                description=r.get("description") or "",
            )
            for r in results
            if r.get("name")
        ]

    def _build_context(
        self,
        chunks: list[dict[str, Any]],
        scores: list[float],
        entities: list[RelatedEntity],
    ) -> str:
        """Build the context string for LLM generation."""
        parts: list[str] = []

        # Source chunks
        parts.append("## Source Passages\n")
        for i, (chunk, score) in enumerate(zip(chunks, scores, strict=True), 1):
            chapter = chunk.get("chapter_number", "?")
            title = chunk.get("chapter_title", "")
            header = f"Chapter {chapter}"
            if title:
                header += f" — {title}"
            parts.append(f"### [{i}] {header} (relevance: {score:.2f})")
            parts.append(chunk["text"])
            parts.append("")

        # Related KG entities
        if entities:
            parts.append("\n## Related Knowledge Graph Entities\n")
            for e in entities:
                desc = f": {e.description}" if e.description else ""
                parts.append(f"- **{e.name}** ({e.label}){desc}")

        return "\n".join(parts)

    @retry_llm_call(max_attempts=2)
    async def _generate_answer(self, query: str, context: str) -> str:
        """Generate an answer using the configured chat LLM via LangChain."""
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = get_langchain_llm(settings.llm_chat)
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=f"{context}\n\n---\n\nQuestion: {query}"),
        ]
        response = await llm.ainvoke(messages)
        content = response.content
        if isinstance(content, str):
            return content or "I wasn't able to generate an answer."
        return "I wasn't able to generate an answer."
