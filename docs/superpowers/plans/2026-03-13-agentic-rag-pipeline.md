# Agentic RAG Pipeline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the linear ChatService with a LangGraph-based Agentic RAG pipeline featuring adaptive routing, hybrid retrieval with RRF fusion, CRAG corrective loops, and multi-turn conversation support.

**Architecture:** LangGraph StateGraph with 3-way router (KG query / hybrid RAG / direct), hybrid retrieval (dense + BM25 + graph traversal fused via RRF), Cohere reranking, LLM-as-judge faithfulness check with corrective retry loop, and AsyncPostgresSaver for multi-turn conversations.

**Tech Stack:** LangGraph >=0.3, Neo4j 5.x (vector + fulltext indexes), Cohere rerank-v3.5, Gemini 2.5 Flash, BAAI/bge-m3, Langfuse >=2.27, FastAPI SSE, psycopg + psycopg-pool

**Spec:** `docs/superpowers/specs/2026-03-13-agentic-rag-pipeline-design.md`

---

## File Structure

### New files to create

```
backend/app/agents/chat/
├── __init__.py              # Export chat_graph (compiled StateGraph)
├── state.py                 # ChatAgentState TypedDict
├── graph.py                 # Graph builder: nodes + edges + compile
├── prompts.py               # Prompt templates (router, generator, judge, rewriter)
└── nodes/
    ├── __init__.py           # Re-export all node functions
    ├── router.py             # classify_intent() → route
    ├── query_transform.py    # transform_query() → transformed_queries
    ├── retrieve.py           # hybrid_retrieve() → fused_results (dense+BM25+graph+RRF)
    ├── rerank.py             # rerank_results() → reranked_chunks
    ├── context_assembly.py   # assemble_context() → context + kg_entities
    ├── generate.py           # generate_answer() → generation + citations
    ├── faithfulness.py       # check_faithfulness() → faithfulness_score
    ├── kg_query.py           # kg_search() → kg_cypher_result
    └── rewrite.py            # rewrite_query() → query (rewritten) + retries

backend/tests/
├── test_chat_state.py        # State schema validation
├── test_hybrid_search.py     # RRF fusion unit tests
├── test_chat_nodes.py        # Individual node tests (mocked LLM/DB)
├── test_chat_graph.py        # Graph integration tests (mocked)
└── test_chat_api_v2.py       # API endpoint tests
```

### Files to modify

```
backend/pyproject.toml                  # Add psycopg[binary], psycopg-pool
backend/app/schemas/chat.py             # Add thread_id, extend ChatRequest/Response
backend/app/services/chat_service.py    # Refactor to thin graph wrapper
backend/app/api/routes/chat.py          # Multi-turn support, new streaming
backend/app/api/dependencies.py         # Add get_chat_graph dependency
backend/langgraph.json                  # Register chat graph
scripts/init_neo4j.cypher               # Tune HNSW params
```

---

## Chunk 1: Foundation — Dependencies, State, Schemas

### Task 1: Add psycopg dependencies

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add psycopg to pyproject.toml**

Add to `dependencies` array:
```toml
"psycopg[binary]>=3.1",
"psycopg-pool>=3.1",
```

- [ ] **Step 2: Install dependencies**

Run: `cd backend && uv sync`
Expected: Clean install with psycopg and psycopg-pool resolved

- [ ] **Step 3: Verify import**

Run: `cd backend && python -c "from psycopg_pool import AsyncConnectionPool; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock
git commit -m "chore: add psycopg dependencies for LangGraph checkpointing"
```

---

### Task 2: Define ChatAgentState

**Files:**
- Create: `backend/app/agents/chat/__init__.py`
- Create: `backend/app/agents/chat/state.py`
- Create: `backend/app/agents/chat/nodes/__init__.py`
- Test: `backend/tests/test_chat_state.py`

- [ ] **Step 1: Write state validation test**

```python
# backend/tests/test_chat_state.py
"""Tests for ChatAgentState schema."""
import operator

from langchain_core.messages import HumanMessage
from langgraph.graph.message import add_messages

from app.agents.chat.state import ChatAgentState


def test_state_has_required_keys():
    """ChatAgentState defines all required keys."""
    hints = ChatAgentState.__annotations__
    required = [
        "messages", "original_query", "query", "route",
        "transformed_queries", "fused_results", "reranked_chunks",
        "kg_entities", "kg_cypher_result", "context", "generation",
        "citations", "faithfulness_score", "faithfulness_reason",
        "retries", "book_id", "max_chapter",
    ]
    for key in required:
        assert key in hints, f"Missing state key: {key}"


def test_state_is_total_false():
    """State uses total=False so nodes can return partial updates."""
    assert ChatAgentState.__total__ is False


def test_messages_uses_add_messages_reducer():
    """The messages field uses LangGraph's add_messages reducer."""
    from typing import get_type_hints, Annotated
    hints = get_type_hints(ChatAgentState, include_extras=True)
    msg_hint = hints["messages"]
    # Annotated[list[BaseMessage], add_messages]
    assert hasattr(msg_hint, "__metadata__")
    assert msg_hint.__metadata__[0] is add_messages


def test_retries_uses_operator_add():
    """The retries field uses operator.add reducer for increment."""
    from typing import get_type_hints
    hints = get_type_hints(ChatAgentState, include_extras=True)
    retries_hint = hints["retries"]
    assert hasattr(retries_hint, "__metadata__")
    assert retries_hint.__metadata__[0] is operator.add
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_chat_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.agents.chat'`

- [ ] **Step 3: Create directory structure and state module**

```python
# backend/app/agents/chat/__init__.py
"""Chat/RAG LangGraph agent.

Exports the compiled chat graph for use by ChatService and LangGraph Studio.
"""
```

```python
# backend/app/agents/chat/nodes/__init__.py
"""Chat agent graph nodes."""
```

```python
# backend/app/agents/chat/state.py
"""LangGraph state definition for the chat/RAG pipeline.

NOTE: This file intentionally does NOT use `from __future__ import annotations`
because LangGraph's StateGraph uses get_type_hints() at runtime to resolve
the state schema. Deferred annotations break this resolution.
"""

import operator
from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class ChatAgentState(TypedDict, total=False):
    """Shared state for the chat/RAG LangGraph pipeline.

    Flows through: router → [kg_query | query_transform → retrieve →
    rerank → context_assembly] → generate → faithfulness_check →
    [END | rewrite → retrieve].
    """

    # -- Conversation (managed by add_messages reducer) --
    messages: Annotated[list[BaseMessage], add_messages]

    # -- Query processing --
    original_query: str
    query: str
    route: str  # kg_query | hybrid_rag | direct
    transformed_queries: list[str]

    # -- Retrieval --
    dense_results: list[dict[str, Any]]
    sparse_results: list[dict[str, Any]]
    graph_results: list[dict[str, Any]]
    fused_results: list[dict[str, Any]]
    reranked_chunks: list[dict[str, Any]]

    # -- KG context --
    kg_entities: list[dict[str, Any]]
    kg_cypher_result: list[dict[str, Any]]

    # -- Generation --
    context: str
    generation: str
    citations: list[dict[str, Any]]

    # -- Quality control --
    faithfulness_score: float
    faithfulness_reason: str
    retries: Annotated[int, operator.add]

    # -- Scope --
    book_id: str
    max_chapter: int | None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_chat_state.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/chat/ backend/tests/test_chat_state.py
git commit -m "feat(chat): add ChatAgentState for agentic RAG pipeline"
```

---

### Task 3: Extend chat schemas for multi-turn

**Files:**
- Modify: `backend/app/schemas/chat.py`
- Test: `backend/tests/test_chat_state.py` (extend)

- [ ] **Step 1: Write schema test**

Append to `backend/tests/test_chat_state.py`:

```python
from app.schemas.chat import ChatRequest, ChatResponse, Citation


def test_chat_request_has_thread_id():
    """ChatRequest accepts optional thread_id for multi-turn."""
    req = ChatRequest(query="test", book_id="b1")
    assert req.thread_id is None

    req2 = ChatRequest(query="test", book_id="b1", thread_id="t-123")
    assert req2.thread_id == "t-123"


def test_chat_response_has_thread_id():
    """ChatResponse returns thread_id."""
    resp = ChatResponse(answer="hi", thread_id="t-123")
    assert resp.thread_id == "t-123"


def test_citation_model():
    """Citation has chapter and optional position."""
    c = Citation(chapter=5)
    assert c.chapter == 5
    assert c.position is None

    c2 = Citation(chapter=5, position=3)
    assert c2.position == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_chat_state.py::test_chat_request_has_thread_id -v`
Expected: FAIL — `ImportError: cannot import name 'Citation'`

- [ ] **Step 3: Update chat schemas**

In `backend/app/schemas/chat.py`, add:

```python
class Citation(BaseModel):
    """A parsed chapter citation from the generated answer."""
    chapter: int
    position: int | None = None


class ChatRequest(BaseModel):
    # ... existing fields ...
    thread_id: str | None = Field(
        default=None, description="Conversation thread ID for multi-turn"
    )


class ChatResponse(BaseModel):
    # ... existing fields ...
    thread_id: str | None = None
    citations: list[Citation] = []
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_chat_state.py -v`
Expected: All PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/chat.py backend/tests/test_chat_state.py
git commit -m "feat(chat): extend schemas with thread_id and Citation model"
```

---

### Task 4: Implement hybrid search with RRF fusion

**Files:**
- Create: `backend/app/agents/chat/nodes/retrieve.py`
- Test: `backend/tests/test_hybrid_search.py`

- [ ] **Step 1: Write RRF fusion unit test**

```python
# backend/tests/test_hybrid_search.py
"""Tests for hybrid search with RRF fusion."""
import pytest

from app.agents.chat.nodes.retrieve import rrf_fuse, RRF_K


def test_rrf_fuse_single_list():
    """RRF with one result list returns ranked scores."""
    results = [
        {"node_id": "a", "text": "t1"},
        {"node_id": "b", "text": "t2"},
        {"node_id": "c", "text": "t3"},
    ]
    fused = rrf_fuse([results], weights=[1.0], top_k=3)
    assert len(fused) == 3
    assert fused[0]["node_id"] == "a"  # rank 0 → highest RRF score
    assert fused[0]["rrf_score"] == pytest.approx(1.0 / (RRF_K + 1))


def test_rrf_fuse_two_lists_boosts_overlap():
    """Documents appearing in both lists get boosted."""
    dense = [
        {"node_id": "a", "text": "t1"},
        {"node_id": "b", "text": "t2"},
    ]
    sparse = [
        {"node_id": "b", "text": "t2"},  # overlap with dense
        {"node_id": "c", "text": "t3"},
    ]
    fused = rrf_fuse([dense, sparse], weights=[1.0, 1.0], top_k=3)
    # "b" appears in both → highest combined score
    assert fused[0]["node_id"] == "b"


def test_rrf_fuse_respects_weights():
    """Higher weight amplifies one list's contribution."""
    list_a = [{"node_id": "x", "text": "tx"}]
    list_b = [{"node_id": "y", "text": "ty"}]
    # Weight list_b much higher
    fused = rrf_fuse([list_a, list_b], weights=[0.1, 10.0], top_k=2)
    assert fused[0]["node_id"] == "y"


def test_rrf_fuse_top_k_limit():
    """Returns at most top_k results."""
    results = [{"node_id": str(i), "text": f"t{i}"} for i in range(20)]
    fused = rrf_fuse([results], weights=[1.0], top_k=5)
    assert len(fused) == 5


def test_rrf_fuse_empty_lists():
    """Empty input returns empty output."""
    fused = rrf_fuse([[], []], weights=[1.0, 1.0], top_k=5)
    assert fused == []


def test_rrf_fuse_preserves_metadata():
    """Fused results preserve all original metadata from first occurrence."""
    results = [
        {"node_id": "a", "text": "hello", "chapter_number": 5, "chapter_title": "Ch5"},
    ]
    fused = rrf_fuse([results], weights=[1.0], top_k=1)
    assert fused[0]["chapter_number"] == 5
    assert fused[0]["chapter_title"] == "Ch5"
    assert "rrf_score" in fused[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_hybrid_search.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement RRF fusion**

```python
# backend/app/agents/chat/nodes/retrieve.py
"""Hybrid retrieval node: dense + BM25 + graph traversal with RRF fusion.

Runs three parallel retrieval arms against Neo4j, then fuses results
using Reciprocal Rank Fusion (RRF) with configurable weights.
"""

import asyncio
from typing import Any

from app.core.logging import get_logger
from app.repositories.base import Neo4jRepository

logger = get_logger(__name__)

RRF_K = 60  # Standard RRF constant


def rrf_fuse(
    result_lists: list[list[dict[str, Any]]],
    weights: list[float],
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Fuse multiple ranked result lists using Reciprocal Rank Fusion.

    Args:
        result_lists: List of ranked result lists. Each result must have "node_id".
        weights: Weight per result list. Higher = more influence on final ranking.
        top_k: Maximum number of results to return.

    Returns:
        Fused results sorted by RRF score descending, with "rrf_score" added.
    """
    scores: dict[str, float] = {}
    metadata: dict[str, dict[str, Any]] = {}

    for result_list, weight in zip(result_lists, weights, strict=True):
        for rank, result in enumerate(result_list):
            nid = result["node_id"]
            scores[nid] = scores.get(nid, 0.0) + weight / (RRF_K + rank + 1)
            if nid not in metadata:
                metadata[nid] = result

    sorted_ids = sorted(scores, key=scores.__getitem__, reverse=True)[:top_k]

    return [
        {**metadata[nid], "rrf_score": scores[nid]}
        for nid in sorted_ids
    ]


def _escape_lucene(query: str) -> str:
    """Escape Lucene special characters for Neo4j fulltext queries."""
    special = r'+-&|!(){}[]^"~*?:\/'
    return "".join(f"\\{c}" if c in special else c for c in query)


async def _dense_search(
    repo: Neo4jRepository,
    query_embedding: list[float],
    book_id: str,
    top_k: int,
    max_chapter: int | None,
) -> list[dict[str, Any]]:
    """Vector similarity search on chunk embeddings."""
    return await repo.execute_read(
        """
        CALL db.index.vector.queryNodes('chunk_embedding', $top_k, $embedding)
        YIELD node AS chunk, score
        MATCH (chap:Chapter)-[:HAS_CHUNK]->(chunk)
        WHERE chap.book_id = $book_id
          AND ($max_chapter IS NULL OR chap.number <= $max_chapter)
        RETURN elementId(chunk) AS node_id,
               chunk.text AS text,
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


async def _sparse_search(
    repo: Neo4jRepository,
    query_text: str,
    book_id: str,
    top_k: int,
    max_chapter: int | None,
) -> list[dict[str, Any]]:
    """BM25 fulltext search on chunk text."""
    escaped = _escape_lucene(query_text)
    if not escaped.strip():
        return []
    return await repo.execute_read(
        """
        CALL db.index.fulltext.queryNodes('chunk_fulltext', $query)
        YIELD node AS chunk, score
        MATCH (chap:Chapter)-[:HAS_CHUNK]->(chunk)
        WHERE chap.book_id = $book_id
          AND ($max_chapter IS NULL OR chap.number <= $max_chapter)
        RETURN elementId(chunk) AS node_id,
               chunk.text AS text,
               chap.number AS chapter_number,
               chap.title AS chapter_title,
               chunk.position AS position,
               score
        ORDER BY score DESC
        LIMIT $top_k
        """,
        {
            "query": escaped,
            "book_id": book_id,
            "top_k": top_k,
            "max_chapter": max_chapter,
        },
    )


async def _graph_search(
    repo: Neo4jRepository,
    query_text: str,
    book_id: str,
    top_k: int,
    max_chapter: int | None,
) -> list[dict[str, Any]]:
    """Entity-centric graph traversal: entity_fulltext → GROUNDED_IN → Chunk."""
    escaped = _escape_lucene(query_text)
    if not escaped.strip():
        return []
    return await repo.execute_read(
        """
        CALL db.index.fulltext.queryNodes('entity_fulltext', $query)
        YIELD node AS entity, score AS entity_score
        WHERE entity_score > 0.5
        WITH entity
        ORDER BY entity_score DESC
        LIMIT 5
        MATCH (entity)-[:GROUNDED_IN|MENTIONED_IN]->(chunk:Chunk)<-[:HAS_CHUNK]-(chap:Chapter)
        WHERE chap.book_id = $book_id
          AND ($max_chapter IS NULL OR chap.number <= $max_chapter)
        RETURN DISTINCT elementId(chunk) AS node_id,
               chunk.text AS text,
               chap.number AS chapter_number,
               chap.title AS chapter_title,
               chunk.position AS position,
               1.0 AS score
        LIMIT $top_k
        """,
        {
            "query": escaped,
            "book_id": book_id,
            "top_k": top_k,
            "max_chapter": max_chapter,
        },
    )


async def hybrid_retrieve(
    repo: Neo4jRepository,
    query_text: str,
    query_embedding: list[float],
    book_id: str,
    *,
    top_k_per_arm: int = 30,
    final_top_k: int = 15,
    max_chapter: int | None = None,
    dense_weight: float = 1.0,
    sparse_weight: float = 1.0,
    graph_weight: float = 0.5,
) -> list[dict[str, Any]]:
    """Run 3-arm hybrid retrieval with RRF fusion.

    Runs dense, sparse, and graph searches in parallel via asyncio.gather(),
    then fuses results using Reciprocal Rank Fusion.
    """
    dense_results, sparse_results, graph_results = await asyncio.gather(
        _dense_search(repo, query_embedding, book_id, top_k_per_arm, max_chapter),
        _sparse_search(repo, query_text, book_id, top_k_per_arm, max_chapter),
        _graph_search(repo, query_text, book_id, top_k_per_arm, max_chapter),
    )

    logger.info(
        "hybrid_retrieval_completed",
        dense_count=len(dense_results),
        sparse_count=len(sparse_results),
        graph_count=len(graph_results),
        book_id=book_id,
    )

    fused = rrf_fuse(
        [dense_results, sparse_results, graph_results],
        weights=[dense_weight, sparse_weight, graph_weight],
        top_k=final_top_k,
    )

    return fused
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_hybrid_search.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/chat/nodes/retrieve.py backend/tests/test_hybrid_search.py
git commit -m "feat(chat): hybrid retrieval with 3-arm RRF fusion"
```

---

## Chunk 2: LangGraph Nodes — Router, Query Transform, Rerank, KG Query

### Task 5: Write prompt templates

**Files:**
- Create: `backend/app/agents/chat/prompts.py`

- [ ] **Step 1: Create prompts module**

```python
# backend/app/agents/chat/prompts.py
"""Prompt templates for the chat/RAG pipeline.

All prompts used by graph nodes are centralized here for easy tuning.
"""

ROUTER_SYSTEM = """\
You are a query router for a fiction novel Q&A system backed by a Knowledge Graph.
Classify the user's question into exactly one category:

- "kg_query": Questions about specific entities, relationships, character stats, \
skills, classes, progression, or "who is X?" / "how are X and Y related?"
- "hybrid_rag": Narrative questions, "why did X happen?", thematic analysis, \
explanations requiring passage evidence
- "direct": Greetings, meta questions ("what can you do?"), out-of-scope questions

Consider the full conversation history for context resolution.
Respond with ONLY the category name, nothing else."""

QUERY_TRANSFORM_SYSTEM = """\
You are a query reformulation engine for a fiction novel Q&A system.
Given a user question, generate exactly 3 alternative formulations that:
1. Use different keywords while preserving the intent
2. Expand abbreviations or character nicknames if present
3. Approach the question from a different angle

Return a JSON array of 3 strings. Nothing else."""

HYDE_SYSTEM = """\
You are an expert on this fiction novel universe. Given a question, write a short \
hypothetical passage (2-3 sentences) that would perfectly answer it, as if quoting \
from the novel. This will be used for retrieval, not shown to the user."""

GENERATOR_SYSTEM = """\
You are WorldRAG, an expert assistant for fiction novel universes.
Answer the user's question using ONLY the provided context from the Knowledge Graph \
and source chunks.

Rules:
- Ground every claim in the provided sources.
- For every factual claim, cite the source chapter inline: [Ch.N]
- Use the passage numbers provided: [1] = source passage 1, etc.
- Keep answers concise but thorough.
- If asked about character progression (levels, skills, classes), be precise with numbers.
- Never invent information not present in the context.
- If the context doesn't contain enough information, say so honestly.
{spoiler_guard}"""

SPOILER_GUARD = """
IMPORTANT: The reader has read up to Chapter {max_chapter}. \
NEVER reveal or hint at any events, character developments, \
or plot points from chapters after Chapter {max_chapter}."""

FAITHFULNESS_SYSTEM = """\
You are a faithfulness judge for a fiction novel Q&A system.
Given the user's question, the retrieved context chunks, and the generated answer, \
evaluate whether the answer is:

1. **Grounded**: Every factual claim is supported by the provided context chunks.
2. **Relevant**: The answer addresses the user's question.

Respond with a JSON object:
{
  "score": <float 0.0-1.0>,
  "grounded": <bool>,
  "relevant": <bool>,
  "reason": "<brief explanation>"
}
Nothing else."""

REWRITE_SYSTEM = """\
You are a query rewriter for a fiction novel Q&A system.
The previous retrieval attempt failed to find good results.

Given the original question and the reason for failure, rewrite the query to:
1. Use more specific entity names or terms
2. Decompose a complex question into a simpler, focused sub-question
3. Try a different angle of approach

Return ONLY the rewritten query string, nothing else."""

KG_QUERY_SYSTEM = """\
You are an entity extraction engine for a fiction novel Knowledge Graph.
Given a user's question about entities, extract:
1. Entity names mentioned (be precise with spelling)
2. The type of query: "entity_lookup", "relationship", "stat_progression", or "skills"

Respond with a JSON object:
{
  "entities": ["Entity Name 1", "Entity Name 2"],
  "query_type": "entity_lookup"
}
Nothing else."""
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/chat/prompts.py
git commit -m "feat(chat): add prompt templates for all RAG pipeline nodes"
```

---

### Task 6: Implement router node

**Files:**
- Create: `backend/app/agents/chat/nodes/router.py`
- Test: `backend/tests/test_chat_nodes.py`

- [ ] **Step 1: Write router test**

```python
# backend/tests/test_chat_nodes.py
"""Tests for individual chat agent nodes."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from langchain_core.messages import HumanMessage, AIMessage


class TestRouterNode:
    """Tests for the router node."""

    @pytest.mark.asyncio
    async def test_routes_entity_question_to_kg_query(self):
        from app.agents.chat.nodes.router import classify_intent

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="kg_query"))

        with patch("app.agents.chat.nodes.router.get_langchain_llm", return_value=mock_llm):
            result = await classify_intent({
                "messages": [HumanMessage(content="Who is Randidly?")],
                "original_query": "Who is Randidly?",
                "query": "Who is Randidly?",
                "book_id": "b1",
            })

        assert result["route"] == "kg_query"

    @pytest.mark.asyncio
    async def test_routes_narrative_to_hybrid_rag(self):
        from app.agents.chat.nodes.router import classify_intent

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="hybrid_rag"))

        with patch("app.agents.chat.nodes.router.get_langchain_llm", return_value=mock_llm):
            result = await classify_intent({
                "messages": [HumanMessage(content="Why did Jake betray the guild?")],
                "original_query": "Why did Jake betray the guild?",
                "query": "Why did Jake betray the guild?",
                "book_id": "b1",
            })

        assert result["route"] == "hybrid_rag"

    @pytest.mark.asyncio
    async def test_routes_greeting_to_direct(self):
        from app.agents.chat.nodes.router import classify_intent

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="direct"))

        with patch("app.agents.chat.nodes.router.get_langchain_llm", return_value=mock_llm):
            result = await classify_intent({
                "messages": [HumanMessage(content="Hello!")],
                "original_query": "Hello!",
                "query": "Hello!",
                "book_id": "b1",
            })

        assert result["route"] == "direct"

    @pytest.mark.asyncio
    async def test_defaults_to_hybrid_rag_on_unknown(self):
        from app.agents.chat.nodes.router import classify_intent

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="something_weird"))

        with patch("app.agents.chat.nodes.router.get_langchain_llm", return_value=mock_llm):
            result = await classify_intent({
                "messages": [HumanMessage(content="test")],
                "original_query": "test",
                "query": "test",
                "book_id": "b1",
            })

        assert result["route"] == "hybrid_rag"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_chat_nodes.py::TestRouterNode -v`
Expected: FAIL

- [ ] **Step 3: Implement router node**

```python
# backend/app/agents/chat/nodes/router.py
"""Router node: classifies user intent into kg_query / hybrid_rag / direct."""

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.chat.prompts import ROUTER_SYSTEM
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm

logger = get_logger(__name__)

VALID_ROUTES = {"kg_query", "hybrid_rag", "direct"}


async def classify_intent(state: dict[str, Any]) -> dict[str, Any]:
    """Classify the user's question intent for routing."""
    llm = get_langchain_llm(settings.llm_chat)

    # Build conversation context for the router
    messages = [
        SystemMessage(content=ROUTER_SYSTEM),
        HumanMessage(content=state["query"]),
    ]

    response = await llm.ainvoke(messages)
    route = response.content.strip().lower()

    if route not in VALID_ROUTES:
        logger.warning("router_unknown_route", raw=route, defaulting="hybrid_rag")
        route = "hybrid_rag"

    logger.info("router_classified", route=route, query_len=len(state["query"]))
    return {"route": route}
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_chat_nodes.py::TestRouterNode -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/chat/nodes/router.py backend/tests/test_chat_nodes.py
git commit -m "feat(chat): implement router node with 3-way intent classification"
```

---

### Task 7: Implement query transform node

**Files:**
- Create: `backend/app/agents/chat/nodes/query_transform.py`
- Test: `backend/tests/test_chat_nodes.py` (extend)

- [ ] **Step 1: Write query transform test**

Append to `backend/tests/test_chat_nodes.py`:

```python
class TestQueryTransformNode:
    """Tests for the query transform node."""

    @pytest.mark.asyncio
    async def test_generates_multiple_queries(self):
        from app.agents.chat.nodes.query_transform import transform_query

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=AIMessage(content='["What class does Randidly have?", "Randidly character class", "Randidly Ghosthound class type"]')
        )

        with patch("app.agents.chat.nodes.query_transform.get_langchain_llm", return_value=mock_llm):
            result = await transform_query({
                "query": "What is Randidly's class?",
                "book_id": "b1",
            })

        assert len(result["transformed_queries"]) == 3
        assert "query" in result  # original preserved in list

    @pytest.mark.asyncio
    async def test_fallback_on_invalid_json(self):
        from app.agents.chat.nodes.query_transform import transform_query

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="not json"))

        with patch("app.agents.chat.nodes.query_transform.get_langchain_llm", return_value=mock_llm):
            result = await transform_query({
                "query": "test query",
                "book_id": "b1",
            })

        # Fallback: just use original query
        assert result["transformed_queries"] == ["test query"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_chat_nodes.py::TestQueryTransformNode -v`
Expected: FAIL

- [ ] **Step 3: Implement query transform**

```python
# backend/app/agents/chat/nodes/query_transform.py
"""Query transform node: multi-query reformulation + optional HyDE."""

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.chat.prompts import QUERY_TRANSFORM_SYSTEM
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm

logger = get_logger(__name__)


async def transform_query(state: dict[str, Any]) -> dict[str, Any]:
    """Generate query reformulations for better retrieval recall."""
    llm = get_langchain_llm(settings.llm_chat)
    query = state["query"]

    messages = [
        SystemMessage(content=QUERY_TRANSFORM_SYSTEM),
        HumanMessage(content=query),
    ]

    response = await llm.ainvoke(messages)

    try:
        variants = json.loads(response.content)
        if not isinstance(variants, list) or not all(isinstance(v, str) for v in variants):
            raise ValueError("Expected list of strings")
    except (json.JSONDecodeError, ValueError):
        logger.warning("query_transform_parse_failed", raw=response.content[:200])
        variants = []

    # Always include the original query
    all_queries = [query] + [v for v in variants if v != query]

    logger.info("query_transform_completed", original=query, variants=len(variants))
    return {"transformed_queries": all_queries}
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_chat_nodes.py::TestQueryTransformNode -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/chat/nodes/query_transform.py backend/tests/test_chat_nodes.py
git commit -m "feat(chat): implement multi-query transform node"
```

---

### Task 8: Implement rerank node

**Files:**
- Create: `backend/app/agents/chat/nodes/rerank.py`
- Test: `backend/tests/test_chat_nodes.py` (extend)

- [ ] **Step 1: Write rerank test**

Append to `backend/tests/test_chat_nodes.py`:

```python
class TestRerankNode:
    """Tests for the rerank node."""

    @pytest.mark.asyncio
    async def test_rerank_with_cohere(self):
        from app.agents.chat.nodes.rerank import rerank_results
        from app.llm.reranker import RerankResult

        mock_reranker = AsyncMock()
        mock_reranker.rerank = AsyncMock(return_value=[
            RerankResult(index=1, text="relevant", relevance_score=0.95),
            RerankResult(index=0, text="less relevant", relevance_score=0.6),
        ])

        state = {
            "query": "test",
            "fused_results": [
                {"node_id": "a", "text": "less relevant", "chapter_number": 1, "rrf_score": 0.5},
                {"node_id": "b", "text": "relevant", "chapter_number": 2, "rrf_score": 0.4},
            ],
        }

        with patch("app.agents.chat.nodes.rerank._get_reranker", return_value=mock_reranker):
            result = await rerank_results(state)

        assert len(result["reranked_chunks"]) == 2
        assert result["reranked_chunks"][0]["node_id"] == "b"  # reranked to top
        assert result["reranked_chunks"][0]["relevance_score"] == 0.95

    @pytest.mark.asyncio
    async def test_rerank_without_cohere_uses_rrf_order(self):
        from app.agents.chat.nodes.rerank import rerank_results

        state = {
            "query": "test",
            "fused_results": [
                {"node_id": "a", "text": "t1", "rrf_score": 0.5},
                {"node_id": "b", "text": "t2", "rrf_score": 0.4},
            ],
        }

        with patch("app.agents.chat.nodes.rerank._get_reranker", return_value=None):
            result = await rerank_results(state)

        # Without reranker, top-N from RRF order
        assert len(result["reranked_chunks"]) == 2
        assert result["reranked_chunks"][0]["node_id"] == "a"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_chat_nodes.py::TestRerankNode -v`
Expected: FAIL

- [ ] **Step 3: Implement rerank node**

```python
# backend/app/agents/chat/nodes/rerank.py
"""Rerank node: cross-encoder reranking via Cohere (optional fallback to RRF order)."""

from typing import Any

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

RERANK_TOP_N = 5
MIN_RELEVANCE = 0.1

_reranker_instance = None


def _get_reranker():
    """Lazy-load Cohere reranker if API key is configured."""
    global _reranker_instance
    if _reranker_instance is None and settings.cohere_api_key:
        from app.llm.reranker import CohereReranker
        _reranker_instance = CohereReranker()
    return _reranker_instance


async def rerank_results(state: dict[str, Any]) -> dict[str, Any]:
    """Rerank fused results using Cohere cross-encoder or fallback to RRF order."""
    fused = state.get("fused_results", [])
    query = state["query"]
    reranker = _get_reranker()

    if not fused:
        return {"reranked_chunks": []}

    if reranker:
        texts = [chunk["text"] for chunk in fused]
        reranked = await reranker.rerank(
            query=query,
            documents=texts,
            top_n=min(RERANK_TOP_N, len(fused)),
            min_relevance=MIN_RELEVANCE,
        )

        result = []
        for r in reranked:
            chunk = {**fused[r.index], "relevance_score": r.relevance_score}
            result.append(chunk)

        logger.info(
            "rerank_completed",
            input_count=len(fused),
            output_count=len(result),
            top_score=result[0]["relevance_score"] if result else 0,
        )
        return {"reranked_chunks": result}

    # No reranker available — use RRF order, take top-N
    top = fused[:RERANK_TOP_N]
    for chunk in top:
        chunk["relevance_score"] = chunk.get("rrf_score", 0.0)

    logger.info("rerank_skipped_no_cohere", output_count=len(top))
    return {"reranked_chunks": top}
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_chat_nodes.py::TestRerankNode -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/chat/nodes/rerank.py backend/tests/test_chat_nodes.py
git commit -m "feat(chat): implement rerank node with Cohere cross-encoder"
```

---

### Task 9: Implement KG query node

**Files:**
- Create: `backend/app/agents/chat/nodes/kg_query.py`
- Test: `backend/tests/test_chat_nodes.py` (extend)

- [ ] **Step 1: Write KG query test**

Append to `backend/tests/test_chat_nodes.py`:

```python
class TestKGQueryNode:
    """Tests for the KG query node."""

    @pytest.mark.asyncio
    async def test_entity_lookup(self):
        from app.agents.chat.nodes.kg_query import kg_search

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(
            content='{"entities": ["Randidly"], "query_type": "entity_lookup"}'
        ))

        mock_repo = AsyncMock()
        # Entity search returns entity data
        mock_repo.execute_read = AsyncMock(side_effect=[
            # entity_fulltext search
            [{"name": "Randidly Ghosthound", "label": "Character",
              "description": "Main protagonist", "score": 5.0}],
            # relationship expansion
            [{"rel_type": "HAS_SKILL", "target_name": "Spear Mastery",
              "target_label": "Skill"}],
            # grounded chunks
            [{"text": "Randidly gripped his spear...", "chapter_number": 1,
              "chapter_title": "Awakening", "node_id": "c1"}],
        ])

        with patch("app.agents.chat.nodes.kg_query.get_langchain_llm", return_value=mock_llm):
            result = await kg_search(
                {"query": "Who is Randidly?", "book_id": "b1", "max_chapter": None},
                repo=mock_repo,
            )

        assert len(result["kg_cypher_result"]) > 0
        assert len(result["kg_entities"]) > 0

    @pytest.mark.asyncio
    async def test_empty_entity_fallback(self):
        from app.agents.chat.nodes.kg_query import kg_search

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(
            content='{"entities": ["NonExistent"], "query_type": "entity_lookup"}'
        ))

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(return_value=[])  # No results

        with patch("app.agents.chat.nodes.kg_query.get_langchain_llm", return_value=mock_llm):
            result = await kg_search(
                {"query": "Who is NonExistent?", "book_id": "b1", "max_chapter": None},
                repo=mock_repo,
            )

        # Should signal fallback to hybrid_rag
        assert result["route"] == "hybrid_rag"
        assert result["kg_cypher_result"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_chat_nodes.py::TestKGQueryNode -v`
Expected: FAIL

- [ ] **Step 3: Implement KG query node**

```python
# backend/app/agents/chat/nodes/kg_query.py
"""KG query node: entity-centric Cypher queries bypassing vector search."""

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.chat.prompts import KG_QUERY_SYSTEM
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm
from app.repositories.base import Neo4jRepository

logger = get_logger(__name__)


async def kg_search(
    state: dict[str, Any],
    *,
    repo: Neo4jRepository,
) -> dict[str, Any]:
    """Search the Knowledge Graph for entity-centric queries.

    If no results found, sets route to 'hybrid_rag' for fallback.
    """
    llm = get_langchain_llm(settings.llm_chat)
    query = state["query"]
    book_id = state["book_id"]
    max_chapter = state.get("max_chapter")

    # Step 1: Extract entity names from query
    response = await llm.ainvoke([
        SystemMessage(content=KG_QUERY_SYSTEM),
        HumanMessage(content=query),
    ])

    try:
        parsed = json.loads(response.content)
        entity_names = parsed.get("entities", [])
        query_type = parsed.get("query_type", "entity_lookup")
    except (json.JSONDecodeError, KeyError):
        logger.warning("kg_query_parse_failed", raw=response.content[:200])
        return {"route": "hybrid_rag", "kg_cypher_result": [], "kg_entities": []}

    if not entity_names:
        return {"route": "hybrid_rag", "kg_cypher_result": [], "kg_entities": []}

    # Step 2: Search entities via fulltext index
    entity_query = " OR ".join(entity_names)
    entities = await repo.execute_read(
        """
        CALL db.index.fulltext.queryNodes('entity_fulltext', $query)
        YIELD node AS entity, score
        WHERE score > 0.5
          AND ($max_chapter IS NULL
               OR NOT exists(entity.valid_from_chapter)
               OR entity.valid_from_chapter <= $max_chapter)
        RETURN entity.name AS name,
               labels(entity)[0] AS label,
               entity.description AS description,
               score
        ORDER BY score DESC
        LIMIT 10
        """,
        {"query": entity_query, "max_chapter": max_chapter},
    )

    if not entities:
        logger.info("kg_query_no_entities_found", query=query)
        return {"route": "hybrid_rag", "kg_cypher_result": [], "kg_entities": []}

    # Step 3: Expand relationships for found entities
    entity_names_found = [e["name"] for e in entities]
    relationships = await repo.execute_read(
        """
        UNWIND $names AS ename
        MATCH (entity {name: ename})-[r]->(related)
        WHERE NOT related:Chunk AND NOT related:Chapter AND NOT related:Book
          AND type(r) <> 'MENTIONED_IN' AND type(r) <> 'GROUNDED_IN'
          AND ($max_chapter IS NULL
               OR NOT exists(r.valid_from_chapter)
               OR r.valid_from_chapter <= $max_chapter)
        RETURN entity.name AS source,
               type(r) AS rel_type,
               related.name AS target_name,
               labels(related)[0] AS target_label
        LIMIT 30
        """,
        {"names": entity_names_found, "max_chapter": max_chapter},
    )

    # Step 4: Fetch grounded chunks
    chunks = await repo.execute_read(
        """
        UNWIND $names AS ename
        MATCH (entity {name: ename})-[:GROUNDED_IN|MENTIONED_IN]->(chunk:Chunk)
              <-[:HAS_CHUNK]-(chap:Chapter)
        WHERE chap.book_id = $book_id
          AND ($max_chapter IS NULL OR chap.number <= $max_chapter)
        RETURN DISTINCT elementId(chunk) AS node_id,
               chunk.text AS text,
               chap.number AS chapter_number,
               chap.title AS chapter_title
        ORDER BY chap.number
        LIMIT 10
        """,
        {"names": entity_names_found, "book_id": book_id, "max_chapter": max_chapter},
    )

    logger.info(
        "kg_query_completed",
        entities_found=len(entities),
        relationships_found=len(relationships),
        chunks_found=len(chunks),
        query_type=query_type,
    )

    return {
        "kg_cypher_result": chunks,
        "kg_entities": [
            {**e, "relationships": [r for r in relationships if r["source"] == e["name"]]}
            for e in entities
        ],
        "reranked_chunks": chunks,  # Pass chunks to context assembly
    }
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_chat_nodes.py::TestKGQueryNode -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/chat/nodes/kg_query.py backend/tests/test_chat_nodes.py
git commit -m "feat(chat): implement KG query node with entity-first retrieval"
```

---

## Chunk 3: Generation, Faithfulness, Rewrite, Context Assembly

### Task 10: Implement context assembly node

**Files:**
- Create: `backend/app/agents/chat/nodes/context_assembly.py`
- Test: `backend/tests/test_chat_nodes.py` (extend)

- [ ] **Step 1: Write context assembly test**

Append to `backend/tests/test_chat_nodes.py`:

```python
class TestContextAssemblyNode:
    @pytest.mark.asyncio
    async def test_builds_context_from_chunks_and_entities(self):
        from app.agents.chat.nodes.context_assembly import assemble_context

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(return_value=[
            {"name": "Jake", "label": "Character", "description": "Archer class"},
        ])

        state = {
            "reranked_chunks": [
                {"text": "Jake fired his bow.", "chapter_number": 5,
                 "chapter_title": "Arena", "relevance_score": 0.9},
            ],
            "book_id": "b1",
            "max_chapter": 10,
        }

        result = await assemble_context(state, repo=mock_repo)
        assert "## Source Passages" in result["context"]
        assert "Chapter 5" in result["context"]
        assert "Jake" in result["context"]
        assert len(result["kg_entities"]) == 1

    @pytest.mark.asyncio
    async def test_empty_chunks_produces_minimal_context(self):
        from app.agents.chat.nodes.context_assembly import assemble_context

        mock_repo = AsyncMock()
        mock_repo.execute_read = AsyncMock(return_value=[])

        result = await assemble_context(
            {"reranked_chunks": [], "book_id": "b1", "max_chapter": None},
            repo=mock_repo,
        )
        assert result["context"] == ""
        assert result["kg_entities"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_chat_nodes.py::TestContextAssemblyNode -v`
Expected: FAIL

- [ ] **Step 3: Implement context assembly**

```python
# backend/app/agents/chat/nodes/context_assembly.py
"""Context assembly node: builds LLM context from chunks + KG entities."""

from typing import Any

from app.core.logging import get_logger
from app.repositories.base import Neo4jRepository

logger = get_logger(__name__)


async def assemble_context(
    state: dict[str, Any],
    *,
    repo: Neo4jRepository,
) -> dict[str, Any]:
    """Build context string from reranked chunks and related KG entities."""
    chunks = state.get("reranked_chunks", [])
    book_id = state["book_id"]
    max_chapter = state.get("max_chapter")

    if not chunks:
        return {"context": "", "kg_entities": []}

    # Fetch related entities from chapters in the retrieved chunks
    chapter_numbers = list({c["chapter_number"] for c in chunks if "chapter_number" in c})

    entities: list[dict[str, Any]] = []
    if chapter_numbers:
        entities = await repo.execute_read(
            """
            MATCH (entity)-[:GROUNDED_IN|MENTIONED_IN]->(chap:Chapter)
            WHERE chap.book_id = $book_id AND chap.number IN $chapters
              AND NOT entity:Chunk AND NOT entity:Book AND NOT entity:Chapter
              AND ($max_chapter IS NULL
                   OR NOT exists(entity.valid_from_chapter)
                   OR entity.valid_from_chapter <= $max_chapter)
            RETURN DISTINCT entity.name AS name,
                   labels(entity)[0] AS label,
                   entity.description AS description
            ORDER BY label, name
            LIMIT 30
            """,
            {"book_id": book_id, "chapters": chapter_numbers, "max_chapter": max_chapter},
        )

    # Use pre-fetched KG entities if available (from kg_query path)
    kg_entities = state.get("kg_entities", []) or [
        {"name": e["name"], "label": e["label"], "description": e.get("description", "")}
        for e in entities
        if e.get("name")
    ]

    # Build context string
    parts: list[str] = []

    parts.append("## Source Passages\n")
    for i, chunk in enumerate(chunks, 1):
        chapter = chunk.get("chapter_number", "?")
        title = chunk.get("chapter_title", "")
        header = f"Chapter {chapter}"
        if title:
            header += f" — {title}"
        score = chunk.get("relevance_score", 0.0)
        parts.append(f"### [{i}] {header} (relevance: {score:.2f})")
        parts.append(chunk.get("text", ""))
        parts.append("")

    if kg_entities:
        parts.append("\n## Related Knowledge Graph Entities\n")
        for e in kg_entities:
            desc = f": {e.get('description', '')}" if e.get("description") else ""
            name = e.get("name", "Unknown")
            label = e.get("label", "Entity")
            rels = e.get("relationships", [])
            parts.append(f"- **{name}** ({label}){desc}")
            for r in rels[:5]:
                parts.append(f"  - {r.get('rel_type', '?')} → {r.get('target_name', '?')} ({r.get('target_label', '?')})")

    context = "\n".join(parts)

    logger.info(
        "context_assembled",
        chunks=len(chunks),
        entities=len(kg_entities),
        context_len=len(context),
    )

    return {"context": context, "kg_entities": kg_entities}
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_chat_nodes.py::TestContextAssemblyNode -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/chat/nodes/context_assembly.py backend/tests/test_chat_nodes.py
git commit -m "feat(chat): implement context assembly node"
```

---

### Task 11: Implement generate node

**Files:**
- Create: `backend/app/agents/chat/nodes/generate.py`
- Test: `backend/tests/test_chat_nodes.py` (extend)

- [ ] **Step 1: Write generate test**

Append to `backend/tests/test_chat_nodes.py`:

```python
import re


class TestGenerateNode:
    @pytest.mark.asyncio
    async def test_generates_answer_with_context(self):
        from app.agents.chat.nodes.generate import generate_answer

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(
            content="Jake is a level 88 Arcane Hunter [Ch.5]. He defeated the Hydra [Ch.5]."
        ))

        state = {
            "query": "Who is Jake?",
            "context": "## Source Passages\n### [1] Chapter 5\nJake is level 88.",
            "messages": [HumanMessage(content="Who is Jake?")],
            "max_chapter": None,
        }

        with patch("app.agents.chat.nodes.generate.get_langchain_llm", return_value=mock_llm):
            result = await generate_answer(state)

        assert "Jake" in result["generation"]
        assert len(result["citations"]) == 2
        assert result["citations"][0]["chapter"] == 5

    @pytest.mark.asyncio
    async def test_empty_context_returns_apology(self):
        from app.agents.chat.nodes.generate import generate_answer

        state = {
            "query": "test",
            "context": "",
            "messages": [HumanMessage(content="test")],
            "max_chapter": None,
        }

        result = await generate_answer(state)
        assert "couldn't find" in result["generation"].lower() or "no relevant" in result["generation"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_chat_nodes.py::TestGenerateNode -v`
Expected: FAIL

- [ ] **Step 3: Implement generate node**

```python
# backend/app/agents/chat/nodes/generate.py
"""Generate node: LLM answer generation with inline chapter citations."""

import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.chat.prompts import GENERATOR_SYSTEM, SPOILER_GUARD
from app.config import settings
from app.core.logging import get_logger
from app.core.resilience import retry_llm_call
from app.llm.providers import get_langchain_llm

logger = get_logger(__name__)

_CITATION_PATTERN = re.compile(r"\[Ch\.(\d+)(?:,\s*p\.(\d+))?\]")


def _parse_citations(text: str) -> list[dict[str, Any]]:
    """Extract [Ch.N] or [Ch.N, p.M] citations from generated text."""
    citations = []
    for match in _CITATION_PATTERN.finditer(text):
        chapter = int(match.group(1))
        position = int(match.group(2)) if match.group(2) else None
        citations.append({"chapter": chapter, "position": position})
    return citations


async def generate_answer(state: dict[str, Any]) -> dict[str, Any]:
    """Generate an answer from the assembled context."""
    context = state.get("context", "")
    query = state["query"]
    max_chapter = state.get("max_chapter")

    if not context:
        return {
            "generation": "I couldn't find any relevant content for your question. "
            "Try rephrasing or asking about something more specific.",
            "citations": [],
        }

    # Build system prompt with optional spoiler guard
    spoiler_text = ""
    if max_chapter is not None:
        spoiler_text = SPOILER_GUARD.format(max_chapter=max_chapter)
    system_prompt = GENERATOR_SYSTEM.format(spoiler_guard=spoiler_text)

    llm = get_langchain_llm(settings.llm_chat)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"{context}\n\n---\n\nQuestion: {query}"),
    ]

    @retry_llm_call(max_attempts=2)
    async def _invoke():
        return await llm.ainvoke(messages)

    response = await _invoke()
    answer = response.content if isinstance(response.content, str) else str(response.content)

    citations = _parse_citations(answer)

    logger.info(
        "generate_completed",
        answer_len=len(answer),
        citation_count=len(citations),
    )

    return {
        "generation": answer,
        "citations": citations,
        "messages": [AIMessage(content=answer)],
    }
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_chat_nodes.py::TestGenerateNode -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/chat/nodes/generate.py backend/tests/test_chat_nodes.py
git commit -m "feat(chat): implement generate node with citation parsing"
```

---

### Task 12: Implement faithfulness check node

**Files:**
- Create: `backend/app/agents/chat/nodes/faithfulness.py`
- Test: `backend/tests/test_chat_nodes.py` (extend)

- [ ] **Step 1: Write faithfulness test**

Append to `backend/tests/test_chat_nodes.py`:

```python
class TestFaithfulnessNode:
    @pytest.mark.asyncio
    async def test_grounded_answer_passes(self):
        from app.agents.chat.nodes.faithfulness import check_faithfulness

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(
            content='{"score": 0.95, "grounded": true, "relevant": true, "reason": "All claims supported."}'
        ))

        state = {
            "query": "Who is Jake?",
            "context": "Jake is an Arcane Hunter.",
            "generation": "Jake is an Arcane Hunter.",
        }

        with patch("app.agents.chat.nodes.faithfulness.get_langchain_llm", return_value=mock_llm):
            result = await check_faithfulness(state)

        assert result["faithfulness_score"] == pytest.approx(0.95)
        assert result["faithfulness_reason"] == "All claims supported."

    @pytest.mark.asyncio
    async def test_ungrounded_answer_fails(self):
        from app.agents.chat.nodes.faithfulness import check_faithfulness

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(
            content='{"score": 0.2, "grounded": false, "relevant": true, "reason": "Claim about level not in context."}'
        ))

        state = {
            "query": "What level is Jake?",
            "context": "Jake is an Arcane Hunter.",
            "generation": "Jake is level 200.",
        }

        with patch("app.agents.chat.nodes.faithfulness.get_langchain_llm", return_value=mock_llm):
            result = await check_faithfulness(state)

        assert result["faithfulness_score"] < 0.5

    @pytest.mark.asyncio
    async def test_parse_failure_defaults_to_pass(self):
        from app.agents.chat.nodes.faithfulness import check_faithfulness

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="not json"))

        with patch("app.agents.chat.nodes.faithfulness.get_langchain_llm", return_value=mock_llm):
            result = await check_faithfulness({
                "query": "test", "context": "ctx", "generation": "gen",
            })

        # On parse failure, default to pass (don't block the user)
        assert result["faithfulness_score"] == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_chat_nodes.py::TestFaithfulnessNode -v`
Expected: FAIL

- [ ] **Step 3: Implement faithfulness check**

```python
# backend/app/agents/chat/nodes/faithfulness.py
"""Faithfulness check node: LLM-as-judge verifying answer groundedness."""

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.chat.prompts import FAITHFULNESS_SYSTEM
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm

logger = get_logger(__name__)


async def check_faithfulness(state: dict[str, Any]) -> dict[str, Any]:
    """Grade the generated answer for faithfulness and relevance."""
    llm = get_langchain_llm(settings.llm_chat)

    judge_input = (
        f"Question: {state['query']}\n\n"
        f"Context:\n{state['context']}\n\n"
        f"Generated Answer:\n{state['generation']}"
    )

    response = await llm.ainvoke([
        SystemMessage(content=FAITHFULNESS_SYSTEM),
        HumanMessage(content=judge_input),
    ])

    try:
        result = json.loads(response.content)
        score = float(result.get("score", 0.0))
        reason = result.get("reason", "")
    except (json.JSONDecodeError, ValueError, TypeError):
        logger.warning("faithfulness_parse_failed", raw=response.content[:200])
        # Default to pass on parse failure — don't block the user
        score = 1.0
        reason = "Judge response unparseable, defaulting to pass"

    logger.info(
        "faithfulness_check_completed",
        score=score,
        reason=reason[:100],
    )

    return {
        "faithfulness_score": score,
        "faithfulness_reason": reason,
    }
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_chat_nodes.py::TestFaithfulnessNode -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/chat/nodes/faithfulness.py backend/tests/test_chat_nodes.py
git commit -m "feat(chat): implement faithfulness check node (LLM-as-judge)"
```

---

### Task 13: Implement rewrite query node

**Files:**
- Create: `backend/app/agents/chat/nodes/rewrite.py`
- Test: `backend/tests/test_chat_nodes.py` (extend)

- [ ] **Step 1: Write rewrite test**

Append to `backend/tests/test_chat_nodes.py`:

```python
class TestRewriteNode:
    @pytest.mark.asyncio
    async def test_rewrites_query(self):
        from app.agents.chat.nodes.rewrite import rewrite_query

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(
            content="What are the specific combat abilities of Randidly Ghosthound?"
        ))

        state = {
            "query": "What can Randidly do?",
            "original_query": "What can Randidly do?",
            "faithfulness_reason": "Answer too vague, not grounded",
        }

        with patch("app.agents.chat.nodes.rewrite.get_langchain_llm", return_value=mock_llm):
            result = await rewrite_query(state)

        assert result["query"] != "What can Randidly do?"
        assert result["retries"] == 1  # Incremented via operator.add

    @pytest.mark.asyncio
    async def test_preserves_original_query(self):
        from app.agents.chat.nodes.rewrite import rewrite_query

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="rewritten"))

        with patch("app.agents.chat.nodes.rewrite.get_langchain_llm", return_value=mock_llm):
            result = await rewrite_query({
                "query": "old", "original_query": "original",
                "faithfulness_reason": "bad",
            })

        # original_query should NOT be overwritten
        assert "original_query" not in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_chat_nodes.py::TestRewriteNode -v`
Expected: FAIL

- [ ] **Step 3: Implement rewrite node**

```python
# backend/app/agents/chat/nodes/rewrite.py
"""Rewrite query node: reformulate the query after failed retrieval/generation."""

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.chat.prompts import REWRITE_SYSTEM
from app.config import settings
from app.core.logging import get_logger
from app.llm.providers import get_langchain_llm

logger = get_logger(__name__)


async def rewrite_query(state: dict[str, Any]) -> dict[str, Any]:
    """Rewrite the query for a corrective retry."""
    llm = get_langchain_llm(settings.llm_chat)
    original = state.get("original_query", state["query"])
    reason = state.get("faithfulness_reason", "Results not relevant enough")

    rewrite_input = (
        f"Original question: {original}\n"
        f"Current query: {state['query']}\n"
        f"Failure reason: {reason}\n\n"
        f"Rewrite the query:"
    )

    response = await llm.ainvoke([
        SystemMessage(content=REWRITE_SYSTEM),
        HumanMessage(content=rewrite_input),
    ])

    new_query = response.content.strip()
    if not new_query:
        new_query = original  # Fallback to original

    logger.info(
        "query_rewritten",
        old=state["query"][:100],
        new=new_query[:100],
        reason=reason[:100],
    )

    return {
        "query": new_query,
        "retries": 1,  # Uses operator.add reducer → increments
    }
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_chat_nodes.py::TestRewriteNode -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/chat/nodes/rewrite.py backend/tests/test_chat_nodes.py
git commit -m "feat(chat): implement rewrite query node for CRAG corrective loop"
```

---

## Chunk 4: Graph Compilation, Service Refactor, API Routes

### Task 14: Compile the LangGraph StateGraph

**Files:**
- Create: `backend/app/agents/chat/graph.py`
- Modify: `backend/app/agents/chat/__init__.py`
- Test: `backend/tests/test_chat_graph.py`

- [ ] **Step 1: Write graph structure test**

```python
# backend/tests/test_chat_graph.py
"""Tests for the chat LangGraph agent graph structure."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from langchain_core.messages import HumanMessage, AIMessage


def test_graph_has_all_nodes():
    """Chat graph contains all expected nodes."""
    from app.agents.chat.graph import build_chat_graph

    mock_repo = MagicMock()
    graph = build_chat_graph(repo=mock_repo)

    node_names = set(graph.nodes.keys())
    expected = {
        "__start__", "router", "query_transform", "retrieve",
        "rerank", "context_assembly", "generate",
        "faithfulness_check", "rewrite_query", "kg_query",
    }
    # __start__ is implicit; check our custom nodes
    assert expected - {"__start__"} <= node_names


def test_graph_compiles():
    """Chat graph compiles without errors."""
    from app.agents.chat.graph import build_chat_graph

    mock_repo = MagicMock()
    graph = build_chat_graph(repo=mock_repo)
    compiled = graph.compile()
    assert compiled is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_chat_graph.py -v`
Expected: FAIL

- [ ] **Step 3: Implement graph builder**

```python
# backend/app/agents/chat/graph.py
"""Chat/RAG LangGraph: compiles the StateGraph with all nodes and edges."""

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.chat.state import ChatAgentState
from app.core.logging import get_logger
from app.llm.embeddings import LocalEmbedder
from app.repositories.base import Neo4jRepository

from .nodes.context_assembly import assemble_context
from .nodes.faithfulness import check_faithfulness
from .nodes.generate import generate_answer
from .nodes.kg_query import kg_search
from .nodes.query_transform import transform_query
from .nodes.rerank import rerank_results
from .nodes.retrieve import hybrid_retrieve
from .nodes.rewrite import rewrite_query
from .nodes.router import classify_intent

logger = get_logger(__name__)

FAITHFULNESS_THRESHOLD = 0.6
MAX_RETRIES = 2


def _route_after_router(state: dict[str, Any]) -> str:
    """Conditional edge after router: dispatch to the right path."""
    route = state.get("route", "hybrid_rag")
    if route == "kg_query":
        return "kg_query"
    if route == "direct":
        return "generate"
    return "query_transform"


def _route_after_kg_query(state: dict[str, Any]) -> str:
    """After KG query: if empty results, fallback to hybrid RAG."""
    if state.get("route") == "hybrid_rag":
        # kg_query set this when no entities found
        return "query_transform"
    return "context_assembly"


def _route_after_faithfulness(state: dict[str, Any]) -> str:
    """After faithfulness check: pass, retry, or give up."""
    score = state.get("faithfulness_score", 1.0)
    retries = state.get("retries", 0)

    if score >= FAITHFULNESS_THRESHOLD:
        return "end"
    if retries >= MAX_RETRIES:
        logger.warning("faithfulness_max_retries", score=score, retries=retries)
        return "end"
    return "rewrite_query"


def build_chat_graph(
    *,
    repo: Neo4jRepository,
    embedder: LocalEmbedder | None = None,
) -> StateGraph:
    """Build the chat agent StateGraph (uncompiled).

    Args:
        repo: Neo4j repository for DB access.
        embedder: Embedding model. If None, creates a default LocalEmbedder.
    """
    if embedder is None:
        embedder = LocalEmbedder()

    # Create node functions that close over repo/embedder
    async def _retrieve_node(state: dict[str, Any]) -> dict[str, Any]:
        queries = state.get("transformed_queries", [state["query"]])
        # Embed the first query (original or primary reformulation)
        query_embedding = await embedder.embed_query(queries[0])
        return {
            "fused_results": await hybrid_retrieve(
                repo,
                query_text=state["query"],
                query_embedding=query_embedding,
                book_id=state["book_id"],
                max_chapter=state.get("max_chapter"),
            ),
        }

    async def _kg_query_node(state: dict[str, Any]) -> dict[str, Any]:
        return await kg_search(state, repo=repo)

    async def _context_assembly_node(state: dict[str, Any]) -> dict[str, Any]:
        return await assemble_context(state, repo=repo)

    # Build graph
    builder = StateGraph(ChatAgentState)

    # Add nodes
    builder.add_node("router", classify_intent)
    builder.add_node("query_transform", transform_query)
    builder.add_node("retrieve", _retrieve_node)
    builder.add_node("rerank", rerank_results)
    builder.add_node("context_assembly", _context_assembly_node)
    builder.add_node("generate", generate_answer)
    builder.add_node("faithfulness_check", check_faithfulness)
    builder.add_node("rewrite_query", rewrite_query)
    builder.add_node("kg_query", _kg_query_node)

    # Edges: START → router
    builder.add_edge(START, "router")

    # Router dispatches to 3 paths
    builder.add_conditional_edges("router", _route_after_router, {
        "kg_query": "kg_query",
        "query_transform": "query_transform",
        "generate": "generate",  # direct path
    })

    # KG query path: may fallback to hybrid
    builder.add_conditional_edges("kg_query", _route_after_kg_query, {
        "context_assembly": "context_assembly",
        "query_transform": "query_transform",
    })

    # Hybrid RAG path: transform → retrieve → rerank → context → generate
    builder.add_edge("query_transform", "retrieve")
    builder.add_edge("retrieve", "rerank")
    builder.add_edge("rerank", "context_assembly")
    builder.add_edge("context_assembly", "generate")

    # Generation → faithfulness check
    builder.add_edge("generate", "faithfulness_check")

    # Faithfulness check: pass → END, fail → rewrite → retrieve
    builder.add_conditional_edges("faithfulness_check", _route_after_faithfulness, {
        "end": END,
        "rewrite_query": "rewrite_query",
    })

    # Rewrite loops back to retrieve
    builder.add_edge("rewrite_query", "retrieve")

    return builder
```

- [ ] **Step 4: Update `__init__.py`**

```python
# backend/app/agents/chat/__init__.py
"""Chat/RAG LangGraph agent.

Exports the compiled chat graph for use by ChatService and LangGraph Studio.
"""

from app.agents.chat.graph import build_chat_graph

__all__ = ["build_chat_graph"]
```

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest tests/test_chat_graph.py -v`
Expected: 2 PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/chat/graph.py backend/app/agents/chat/__init__.py backend/tests/test_chat_graph.py
git commit -m "feat(chat): compile LangGraph StateGraph with all nodes and edges"
```

---

### Task 15: Refactor ChatService as graph wrapper

**Files:**
- Modify: `backend/app/services/chat_service.py`
- Modify: `backend/app/schemas/chat.py`
- Test: `backend/tests/test_chat_service.py` (update existing)

- [ ] **Step 1: Read existing test**

Run: Read `backend/tests/test_chat_service.py` to understand current test patterns before modifying.

- [ ] **Step 2: Write new ChatService test for graph-based query**

Create `backend/tests/test_chat_service_v2.py`:

```python
# backend/tests/test_chat_service_v2.py
"""Tests for refactored ChatService (LangGraph wrapper)."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from langchain_core.messages import AIMessage


@pytest.mark.asyncio
async def test_chat_service_query_invokes_graph():
    """ChatService.query() invokes the compiled LangGraph."""
    from app.services.chat_service import ChatService

    mock_driver = MagicMock()
    service = ChatService(mock_driver)

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value={
        "generation": "Jake is an Arcane Hunter.",
        "citations": [{"chapter": 5, "position": None}],
        "reranked_chunks": [
            {"text": "Jake fired...", "chapter_number": 5,
             "chapter_title": "Arena", "relevance_score": 0.9},
        ],
        "kg_entities": [
            {"name": "Jake", "label": "Character", "description": "Archer"},
        ],
        "messages": [AIMessage(content="Jake is an Arcane Hunter.")],
    })

    with patch.object(service, "_get_compiled_graph", return_value=mock_graph):
        result = await service.query(
            query="Who is Jake?",
            book_id="b1",
            top_k=20,
        )

    assert result.answer == "Jake is an Arcane Hunter."
    assert len(result.sources) > 0
    mock_graph.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_chat_service_passes_thread_id():
    """Thread ID is passed to graph config for multi-turn."""
    from app.services.chat_service import ChatService

    mock_driver = MagicMock()
    service = ChatService(mock_driver)

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(return_value={
        "generation": "answer",
        "citations": [],
        "reranked_chunks": [],
        "kg_entities": [],
        "messages": [AIMessage(content="answer")],
    })

    with patch.object(service, "_get_compiled_graph", return_value=mock_graph):
        await service.query(query="test", book_id="b1", thread_id="t-123")

    call_config = mock_graph.ainvoke.call_args[1].get("config", {})
    assert call_config["configurable"]["thread_id"] == "t-123"
```

- [ ] **Step 3: Refactor ChatService**

Rewrite `backend/app/services/chat_service.py` to wrap the LangGraph. Keep the old implementation commented or as a fallback initially — the graph-based path is the primary path.

The key changes:
- `__init__` builds the graph
- `query()` invokes `graph.ainvoke()` with state input
- `query_stream()` uses `graph.astream()` with `stream_mode=["messages", "custom"]`
- Old vector search / context building methods removed (now in graph nodes)

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_chat_service_v2.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/chat_service.py backend/tests/test_chat_service_v2.py
git commit -m "refactor(chat): ChatService wraps LangGraph instead of linear pipeline"
```

---

### Task 16: Update API routes for multi-turn + streaming

**Files:**
- Modify: `backend/app/api/routes/chat.py`
- Modify: `backend/app/api/dependencies.py`
- Test: `backend/tests/test_chat_api_v2.py`

- [ ] **Step 1: Write API test**

```python
# backend/tests/test_chat_api_v2.py
"""Tests for updated chat API endpoints."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.schemas.chat import ChatResponse


@pytest.mark.asyncio
async def test_chat_query_accepts_thread_id():
    """POST /chat/query accepts thread_id parameter."""
    from app.schemas.chat import ChatRequest

    req = ChatRequest(query="test", book_id="b1", thread_id="t-abc")
    assert req.thread_id == "t-abc"


@pytest.mark.asyncio
async def test_chat_response_includes_citations():
    """ChatResponse includes parsed citations."""
    from app.schemas.chat import Citation

    resp = ChatResponse(
        answer="Jake is level 88 [Ch.5].",
        citations=[Citation(chapter=5)],
        thread_id="t-abc",
    )
    assert len(resp.citations) == 1
    assert resp.citations[0].chapter == 5
```

- [ ] **Step 2: Update API route**

Add `thread_id` parameter to the POST endpoint and pass it to ChatService.
Update the stream endpoint to accept `thread_id` as a query parameter.

- [ ] **Step 3: Run tests**

Run: `cd backend && python -m pytest tests/test_chat_api_v2.py -v`
Expected: PASSED

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/routes/chat.py backend/app/api/dependencies.py backend/tests/test_chat_api_v2.py
git commit -m "feat(chat): update API routes with multi-turn thread_id support"
```

---

## Chunk 5: Langfuse, LangGraph Studio, HNSW Tuning

### Task 17: Wire Langfuse observability

**Files:**
- Modify: `backend/app/agents/chat/graph.py` (add callback handler)
- Modify: `backend/app/services/chat_service.py` (pass callbacks in config)

- [ ] **Step 1: Add Langfuse callback to ChatService config**

In `ChatService.query()`, when invoking the graph, pass:

```python
from langfuse.langchain import CallbackHandler as LangfuseHandler

callbacks = []
if settings.langfuse_secret_key:
    callbacks.append(LangfuseHandler(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
        session_id=thread_id,
        user_id=user_id,
    ))

config = {
    "configurable": {"thread_id": thread_id},
    "callbacks": callbacks,
}
```

- [ ] **Step 2: Add manual Langfuse span to rerank node**

In `backend/app/agents/chat/nodes/rerank.py`, add optional Langfuse span:

```python
# After reranking
if settings.langfuse_secret_key:
    from langfuse import Langfuse
    langfuse = Langfuse()
    # Score the rerank quality in the current trace
    # (The trace is auto-created by the callback handler)
```

- [ ] **Step 3: Test with Langfuse disabled (no crash)**

Run: `cd backend && python -m pytest tests/test_chat_nodes.py -v`
Expected: All PASSED (Langfuse disabled in tests, no crash)

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/chat_service.py backend/app/agents/chat/nodes/rerank.py
git commit -m "feat(chat): wire Langfuse observability into RAG pipeline"
```

---

### Task 18: Register chat graph in langgraph.json

**Files:**
- Modify: `backend/langgraph.json`

- [ ] **Step 1: Read current langgraph.json**

Run: Read `backend/langgraph.json`

- [ ] **Step 2: Update langgraph.json**

```json
{
  "dependencies": ["."],
  "graphs": {
    "extraction": "./app/services/extraction/__init__.py:extraction_graph",
    "chat": "./app/agents/chat/__init__.py:chat_graph"
  },
  "env": "../.env"
}
```

Note: `chat_graph` needs to be exported from `__init__.py`. Update the `__init__.py` to build and compile a default graph for Studio (using a lazy-loaded repo).

- [ ] **Step 3: Commit**

```bash
git add backend/langgraph.json backend/app/agents/chat/__init__.py
git commit -m "feat(studio): register chat graph in langgraph.json for LangGraph Studio"
```

---

### Task 19: Tune HNSW vector index parameters

**Files:**
- Modify: `scripts/init_neo4j.cypher`

- [ ] **Step 1: Read current vector index definition**

Find the `CREATE VECTOR INDEX chunk_embedding` statement in `scripts/init_neo4j.cypher`.

- [ ] **Step 2: Update HNSW parameters**

Change to:

```cypher
CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS
FOR (c:Chunk) ON (c.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 1024,
    `vector.similarity_function`: 'cosine',
    `vector.hnsw.m`: 24,
    `vector.hnsw.ef_construction`: 200,
    `vector.quantization.enabled`: false
  }
};
```

Note: This change only affects new index creation. Existing indexes need to be dropped and recreated to pick up new HNSW params.

- [ ] **Step 3: Commit**

```bash
git add scripts/init_neo4j.cypher
git commit -m "perf: tune HNSW vector index params (m=24, ef_construction=200)"
```

---

### Task 20: Update nodes/__init__.py re-exports

**Files:**
- Modify: `backend/app/agents/chat/nodes/__init__.py`

- [ ] **Step 1: Add re-exports**

```python
# backend/app/agents/chat/nodes/__init__.py
"""Chat agent graph nodes."""

from app.agents.chat.nodes.context_assembly import assemble_context
from app.agents.chat.nodes.faithfulness import check_faithfulness
from app.agents.chat.nodes.generate import generate_answer
from app.agents.chat.nodes.kg_query import kg_search
from app.agents.chat.nodes.query_transform import transform_query
from app.agents.chat.nodes.rerank import rerank_results
from app.agents.chat.nodes.retrieve import hybrid_retrieve, rrf_fuse
from app.agents.chat.nodes.rewrite import rewrite_query
from app.agents.chat.nodes.router import classify_intent

__all__ = [
    "assemble_context",
    "check_faithfulness",
    "classify_intent",
    "generate_answer",
    "hybrid_retrieve",
    "kg_search",
    "rerank_results",
    "rewrite_query",
    "rrf_fuse",
    "transform_query",
]
```

- [ ] **Step 2: Run full test suite**

Run: `cd backend && python -m pytest tests/test_chat_state.py tests/test_hybrid_search.py tests/test_chat_nodes.py tests/test_chat_graph.py -v`
Expected: All PASSED

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/chat/nodes/__init__.py
git commit -m "chore: add node re-exports for chat agent"
```

---

### Task 21: Final integration test

- [ ] **Step 1: Run full test suite**

Run: `cd backend && python -m pytest tests/ -x -v --timeout=30`
Expected: All tests pass, no regressions

- [ ] **Step 2: Lint and type check**

Run: `cd backend && python -m ruff check app/agents/chat/ --fix && python -m ruff format app/agents/chat/`
Expected: Clean

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat(chat): complete agentic RAG pipeline with LangGraph

Implements SOTA agentic RAG for fiction novel Q&A:
- 3-way adaptive router (KG query / hybrid RAG / direct)
- Hybrid retrieval: dense + BM25 + graph traversal with RRF fusion
- Cohere rerank-v3.5 cross-encoder
- CRAG corrective loop with faithfulness check
- Multi-turn conversations via AsyncPostgresSaver
- Langfuse observability
- LangGraph Studio support
"
```
