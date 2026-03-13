# Agentic RAG Pipeline — Design Specification

**Date**: 2026-03-13
**Status**: Approved
**Scope**: Chat/Query RAG pipeline for WorldRAG fiction novel Q&A

---

## 1. Overview

Replace the existing linear `ChatService` (vector search → rerank → LLM) with a LangGraph-based Agentic RAG pipeline featuring adaptive routing, hybrid retrieval with RRF fusion, corrective loops, and multi-turn conversation support.

**Design principles**:
- Async-first (all IO awaited, parallel where possible)
- Entity-aware (leverage the existing Neo4j Knowledge Graph)
- Temporally-scoped (spoiler protection via chapter bounds)
- Observable (Langfuse tracing on every node)
- Self-correcting (CRAG pattern with faithfulness verification)

---

## 2. Graph Architecture

```
START (HumanMessage + thread_id)
  │
  ▼
ROUTER ─── classifies intent ──┬── kg_query
  │                             ├── hybrid_rag
  │                             └── direct
  │
  ├─[kg_query]──► KG_QUERY (Cypher gen) ──┬► GENERATE
  │                                       └► (empty?) fallback to QUERY_TRANSFORM
  │
  ├─[direct]──► GENERATE
  │
  └─[hybrid_rag]──► QUERY_TRANSFORM (multi-query + optional HyDE)
                          │
                    RETRIEVE (fan-out: dense + BM25 + graph → RRF)
                          │
                    RERANK (Cohere rerank-v3.5)
                          │
                    CONTEXT_ASSEMBLY (chunks + KG entities + rels)
                          │
                    GENERATE (LLM + inline citations)
                          │
                    FAITHFULNESS_CHECK (LLM-as-judge)
                          │
                    DECIDE ─── pass → END
                       │
                       └── fail (retries < 2) → REWRITE → RETRIEVE
```

### Nodes

| Node | Purpose | LLM call? |
|------|---------|-----------|
| `router` | Classify intent: kg_query, hybrid_rag, direct | Yes (structured output) |
| `query_transform` | Generate 3 query reformulations + optional HyDE | Yes |
| `retrieve` | Fan-out: vector + BM25 + graph traversal → RRF merge | No |
| `rerank` | Cohere rerank-v3.5 on fused results | API call |
| `context_assembly` | Build context from chunks + KG entities + temporal filter | No |
| `kg_query` | Generate + execute Cypher for entity-centric queries | Yes |
| `generate` | Answer with inline citations [Ch.N] | Yes (streaming) |
| `faithfulness_check` | Grade: is answer grounded in sources? | Yes (structured) |
| `decide` | Conditional edge: pass → END, fail → rewrite | No (logic only) |
| `rewrite_query` | Rewrite query based on failure reason | Yes |

---

## 3. State Schema

**IMPORTANT**: `state.py` must NOT use `from __future__ import annotations` — LangGraph's
`StateGraph` uses `get_type_hints()` at runtime and deferred annotations break resolution.
(Same constraint as the existing `backend/app/agents/state.py`.)

`thread_id` is passed via LangGraph config (`config={"configurable": {"thread_id": ...}}`),
not as a state field — nodes access it via `RunnableConfig` if needed for logging.

```python
class ChatAgentState(TypedDict, total=False):
    # Conversation (managed by add_messages reducer)
    messages: Annotated[list[BaseMessage], add_messages]

    # Query processing
    original_query: str           # Preserved user question
    query: str                    # Current query (potentially rewritten)
    route: str                    # kg_query | hybrid_rag | direct
    transformed_queries: list[str] # Multi-query reformulations

    # Retrieval
    dense_results: list[dict]     # Vector search results
    sparse_results: list[dict]    # BM25 fulltext results
    graph_results: list[dict]     # Entity-centric graph results
    fused_results: list[dict]     # After RRF fusion
    reranked_chunks: list[dict]   # After Cohere reranking

    # KG context
    kg_entities: list[dict]       # Related entities with relationships
    kg_cypher_result: list[dict]  # Direct Cypher query results

    # Generation
    context: str                  # Assembled context for LLM
    generation: str               # LLM answer
    citations: list[dict]         # Parsed [Ch.N] references
                                  # Schema: {"chapter": int, "position": int | None}

    # Quality control
    faithfulness_score: float     # 0-1 from judge
    faithfulness_reason: str      # Why it passed/failed
    retries: Annotated[int, operator.add]  # Corrective loop counter (max 2)
                                           # Each rewrite_query returns {"retries": 1}

    # Scope
    book_id: str
    max_chapter: int | None       # Spoiler guard
```

---

## 4. Hybrid Retrieval with RRF

Three parallel retrieval arms, fused via Reciprocal Rank Fusion:

### 4.1 Dense Search (Neo4j Vector Index)
- Index: `chunk_embedding` (HNSW, 1024d, cosine, m=24, ef_construction=200)
- Query: embed user query with LocalEmbedder (bge-m3)
- Return top-30 chunks scoped to book_id + max_chapter

### 4.2 Sparse Search (Neo4j Fulltext Index)
- Index: `chunk_fulltext` (BM25/Lucene)
- Query: escaped user query text
- Return top-30 chunks scoped to book_id + max_chapter
- Critical for exact entity names, skill names, stat values

### 4.3 Graph Traversal
- From entities matching the query (via `entity_fulltext` index)
- Follow GROUNDED_IN|MENTIONED_IN → Chunk relationships
- Return chunks where relevant entities are grounded
- Enriches with entity context not captured by text search

### 4.4 RRF Fusion
```
score(doc) = Σ weight_i / (k + rank_i)
k = 60, weights: dense=1.0, sparse=1.0, graph=0.5
```
- Implemented in Python with `asyncio.gather()` for parallel search
- Returns top-10 fused results for reranking

---

## 5. Router Logic

LLM structured output with 3 categories:

| Route | Trigger patterns | Examples |
|-------|-----------------|----------|
| `kg_query` | Entity lookup, relationship, stats, progression | "who is X?", "X's skills", "how are X and Y related?", "level at chapter N" |
| `hybrid_rag` | Narrative, analytical, why/how, thematic | "why did X betray Y?", "what happened at the tournament?", "explain the magic system" |
| `direct` | Meta, greetings, clarification, out-of-scope | "hello", "what can you do?", "which books are available?" |

---

## 6. KG Query Path

For entity-centric questions, bypass vector search entirely:

1. Extract entity names from query (LLM structured output)
2. Fulltext search on `entity_fulltext` index
3. Fetch entity properties + relationships (1-2 hops)
4. Fetch grounded chunks via `[:GROUNDED_IN|MENTIONED_IN]`
5. Apply temporal filter (valid_from_chapter <= max_chapter)
6. **If results empty**: fallback to `hybrid_rag` path (set `route = "hybrid_rag"`)
7. Pass entity profile + evidence chunks to GENERATE

Cypher patterns:
- Entity lookup: properties + description
- Relationship: `shortestPath((a)-[:KNOWS|ALLIED_WITH|ENEMY_OF|MEMBER_OF*..3]-(b))` — bounded to 3 hops with explicit relationship types to prevent full-graph traversal. Requires both entity endpoints to be resolved; if only one is found, use 1-hop neighborhood expansion instead.
- Stat progression: CharacterState snapshots ordered by chapter
- Skills/Classes: `(char)-[:HAS_SKILL|HAS_CLASS]->(s)` with temporal bounds

---

## 7. Faithfulness Check (CRAG)

Post-generation LLM-as-judge with structured output:

```
Input: {question, context_chunks, generation}
Output: {
  score: 0.0-1.0,
  grounded: bool,      # All claims supported by sources?
  relevant: bool,      # Addresses the question?
  reason: str          # Brief explanation
}
```

Decision logic:
- `grounded AND relevant` → END (return answer)
- `NOT grounded` → REWRITE (rephrase for better retrieval)
- `NOT relevant` → REWRITE (decompose or step-back)
- `retries >= 2` → END (return best attempt with warning)

---

## 8. Multi-Turn Conversations

- **Checkpointer**: `AsyncPostgresSaver` from `langgraph-checkpoint-postgres>=2.0`
- **Driver**: `psycopg[binary]` (required by langgraph-checkpoint-postgres). **Note**: the project currently uses `asyncpg` for other PostgreSQL access — `psycopg` must be added as a dependency.
- **Thread ID**: `chat-{user_id}-{conversation_id}` (UUID), passed via `config={"configurable": {"thread_id": ...}}`
- **Message history**: Managed by `add_messages` reducer
- **Context resolution**: The router receives full message history to resolve pronouns ("tell me more about him")

Setup:
```python
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

pool = AsyncConnectionPool(
    conninfo=POSTGRES_URI,
    max_size=10,
    kwargs={"autocommit": True, "row_factory": dict_row},
)
checkpointer = AsyncPostgresSaver(pool)
await checkpointer.setup()  # Creates checkpoint tables on first run
graph = builder.compile(checkpointer=checkpointer)
```

**Prerequisite**: Add `psycopg[binary]>=3.1` and `psycopg-pool>=3.1` to `pyproject.toml`.

---

## 9. Streaming

FastAPI SSE endpoint using LangGraph v2 streaming:

```python
stream_mode=["messages", "custom"]
```

Events:
- `custom`: Progress updates from nodes (via `get_stream_writer()`)
  - `{"step": "routing", "route": "hybrid_rag"}`
  - `{"step": "retrieving", "chunks_found": 30}`
  - `{"step": "reranking", "top_score": 0.92}`
- `messages`: Token-by-token generation from GENERATE node
- Final: sources + entities + citations metadata

---

## 10. Observability (Langfuse)

### Integration pattern
- `CallbackHandler` passed via `config={"callbacks": [handler]}` on every `graph.ainvoke()`/`graph.astream()`
- Auto-captures: graph structure, LLM calls, token usage, latency per node

### Manual spans
- Cohere reranker: custom span with scores + billed units
- Neo4j queries: custom spans with query + result counts
- RRF fusion: custom span with per-arm result counts

### Scoring
- `faithfulness_score` pushed per-trace after FAITHFULNESS_CHECK
- `rerank_top_score` pushed per-trace after RERANK
- Session-level scores for multi-turn quality

### Session tracking
- Pass `session_id` and `user_id` via `CallbackHandler(session_id=thread_id, user_id=user_id)` — create a fresh handler per request with scoped IDs
- Alternative: use `langfuse.start_as_current_observation()` context manager with `session_id` kwarg for manual span trees

---

## 11. Spoiler Protection

Multi-layer defense:

1. **Chunk retrieval**: `WHERE chap.number <= $max_chapter` (already exists)
2. **Entity descriptions**: `WHERE entity.valid_from_chapter <= $max_chapter`
3. **Relationship revelation**: `WHERE rel.valid_from_chapter <= $max_chapter`
4. **System prompt**: "The reader has read up to Chapter {max_chapter}. Never reveal events, developments, or plot points from later chapters."
5. **Entity versioning**: Descriptions scoped to what is known at the reader's current chapter

---

## 12. File Structure

```
backend/app/agents/chat/
├── __init__.py              # Export chat_graph
├── state.py                 # ChatAgentState
├── graph.py                 # StateGraph compilation + conditional edges
├── prompts.py               # All prompt templates (router, generator, judge)
└── nodes/
    ├── __init__.py
    ├── router.py            # Intent classification
    ├── query_transform.py   # Multi-query + HyDE
    ├── retrieve.py          # Hybrid retrieval (dense+BM25+graph) + RRF
    ├── rerank.py            # Cohere reranker wrapper
    ├── context_assembly.py  # Build context + temporal filter
    ├── generate.py          # LLM generation with citations
    ├── faithfulness.py      # LLM-as-judge
    └── kg_query.py          # Cypher generation + execution

backend/app/services/
├── chat_service.py          # Refactored: thin wrapper calling graph
└── retrieval/
    ├── __init__.py
    ├── hybrid_search.py     # RRF fusion implementation
    └── graph_retrieval.py   # Entity-centric Cypher queries
```

---

## 13. Technologies

| Component | Technology | Version (pyproject.toml) |
|-----------|-----------|---------|
| Orchestration | LangGraph | `>=0.3` |
| State checkpointing | langgraph-checkpoint-postgres | `>=2.0` |
| Checkpointer driver | psycopg + psycopg-pool | `>=3.1` (NEW — must add) |
| LLM (generation) | Gemini 2.5 Flash | via langchain-google-genai |
| LLM (judge/router) | Gemini 2.5 Flash | via langchain-google-genai |
| Embeddings | BAAI/bge-m3 (local, CUDA) | sentence-transformers |
| Reranker | Cohere rerank-v3.5 | cohere SDK |
| Vector DB | Neo4j 5.x vector index | HNSW cosine 1024d |
| Sparse search | Neo4j 5.x fulltext index | BM25/Lucene |
| Graph DB | Neo4j 5.x | Cypher |
| Observability | Langfuse v2 server (self-hosted) | langfuse SDK `>=2.27` |
| Task queue | arq + Redis | For async evaluation jobs |
| Streaming | FastAPI SSE | StreamingResponse |

---

## 14. What is NOT in scope (future work)

- Contextual Retrieval (prepending chapter context to chunks before embedding) — high ROI but requires re-embedding all chunks
- RAGAS automated evaluation pipeline — build after pipeline is stable
- Community summarization (GraphRAG-style) — future optimization
- Entity embedding index — future, would enable entity-level vector search
- Langfuse v3 server upgrade (ClickHouse + MinIO) — future, v2 server sufficient for now
