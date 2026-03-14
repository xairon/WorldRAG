<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-blue?logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Neo4j-5.x-008CC1?logo=neo4j&logoColor=white" alt="Neo4j">
  <img src="https://img.shields.io/badge/Next.js-16-000000?logo=next.js&logoColor=white" alt="Next.js 16">
  <img src="https://img.shields.io/badge/LangGraph-0.3+-1C3C3C?logo=langchain&logoColor=white" alt="LangGraph">
  <img src="https://img.shields.io/badge/Tests-810%20passing-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

# WorldRAG

**SOTA Knowledge Graph construction + RAG chat system for fiction novel universes.**

Transform novels (LitRPG, fantasy, sci-fi) into rich, queryable Knowledge Graphs, then chat with them using a SOTA 17-node adaptive RAG pipeline. WorldRAG extracts characters, relationships, skills, events, locations, and lore from books — builds a temporally-aware Neo4j graph that evolves chapter by chapter — and answers questions with hybrid vector+BM25 retrieval, NLI faithfulness checking, and conversation memory.

> Built for series like *The Primal Hunter*, *Defiance of the Fall*, *He Who Fights With Monsters* — but works with any fiction genre.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Pipeline Overview](#pipeline-overview)
- [Chat Pipeline Details](#chat-pipeline-details)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Ontology](#ontology)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [What's Implemented vs TODO](#whats-implemented-vs-todo)

---

## Features

### Knowledge Graph Construction (Priority #1)

- **Multi-format ingestion**: ePub, PDF, TXT with automatic chapter detection
- **5-pass extraction pipeline**:
  - **Pass 0** (Regex): Free, instant extraction of blue boxes, level-ups, skill acquisitions, stat increases
  - **Pass 1** (LLM): Characters & relationships
  - **Pass 2** (LLM): Systems & progression (classes, skills, titles, levels)
  - **Pass 3** (LLM): Events & timeline
  - **Pass 4** (LLM): Lore & worldbuilding (locations, items, creatures, factions, concepts)
- **Smart pass routing**: Only runs LLM passes that are relevant (keyword & regex-based detection)
- **3-tier entity deduplication**: Exact match → Fuzzy (thefuzz) → LLM-as-Judge (Instructor)
- **Cross-pass reconciliation**: Unified alias resolution across all extraction passes
- **Temporal modeling**: Chapter-based temporality on all relationships (`valid_from_chapter` / `valid_to_chapter`)
- **Source grounding**: Every entity links back to its source text with character offsets
- **Academic ontology**: Based on CIDOC-CRM, SEM, DOLCE, OntoMedia, FRBRoo/LRMoo, and GOLEM

### SOTA Chat / RAG Pipeline

- **6-route adaptive intent router**: `factual_lookup`, `entity_qa`, `relationship_qa`, `timeline_qa`, `analytical`, `conversational`
- **HyDE + multi-query expansion**: Hypothetical Document Embeddings for improved retrieval
- **Hybrid retrieval**: Vector (BGE-M3) + BM25 + RRF fusion
- **Local CrossEncoder reranker**: zerank-1-small (no Cohere API dependency)
- **Cosine similarity dedup**: >80% threshold for result deduplication
- **Temporal sort**: Dedicated ordering for timeline queries
- **KG lookup path**: Direct graph traversal with fallback to hybrid RAG
- **Structured generation with CoT**: For analytical and timeline routes
- **NLI faithfulness check**: DeBERTa-v3-large with adaptive thresholds per route
- **Faithfulness-driven rewrite loop**: Max 2 retries on faithfulness failure
- **Conversation memory**: Sliding window + Qwen3.5-4B summarization every 5 turns
- **PostgreSQL checkpointing**: LangGraph AsyncPostgresSaver
- **SSE streaming**: Token + source events over Server-Sent Events
- **Chat feedback**: POST/GET `/api/chat/feedback` → PostgreSQL `chat_feedback` table

### Frontend

- **Next.js chat UI**: Thread sidebar, collapsible source panel
- **Citation highlights**: `[Ch.N, §P]` in-line citations
- **Confidence badge**: Per-response faithfulness indicator
- **Feedback**: Thumbs up/down stored in PostgreSQL

### Infrastructure

- **Cost optimization**: Model tiering (Gemini Flash for extraction, local models for aux tasks), per-chapter cost ceilings
- **Resilience**: Circuit breakers per LLM provider, exponential backoff retries, dead letter queue
- **Monitoring**: Full LangFuse integration (traces, spans, cost tracking), structured logging (structlog)
- **Observability**: Health checks for all services (Neo4j, Redis, PostgreSQL, LangFuse)

---

## Architecture

```
                    ePub/PDF/TXT
                         |
                    [Ingestion]
                         |
              Parse -> Chapters -> Chunks
                         |
                 [Regex Extraction]    (Pass 0 — $0 cost)
                         |
              +----------+----------+----------+
              |          |          |          |
         [Characters] [Systems] [Events]   [Lore]    (Passes 1-4 — LLM)
              |          |          |          |
              +----------+----------+----------+
                         |
                 [Reconciliation]
                  Dedup + Aliases
                         |
                    [Neo4j KG]
                  +-------------+
                  | Characters  |--RELATES_TO--> Characters
                  |   Skills    |--HAS_SKILL--> Characters
                  |   Events    |--PARTICIPATES--> Characters
                  | Locations   |--OCCURS_AT--> Events
                  |   Items     |--POSSESSES--> Characters
                  +-------------+
                         |
                 [VoyageAI Embeddings]
                  voyage-3.5 batch
                         |
                    [Chat / RAG]
                         |
              +----------+-----------+
              |    6-Route Intent    |
              |       Router         |
              +----------+-----------+
                         |
              +----------+----------+
              |          |          |
        [KG Lookup] [HyDE+Multi] [Direct]
              |       Query         |
              |          |          |
              +--[Hybrid Retrieve]--+
                 Vector+BM25+RRF
                         |
                  [CrossEncoder]
                    Reranker
                         |
                  [NLI Faithfulness]
                    DeBERTa-v3
                         |
                   [SSE Stream]
                  Token + Sources
```

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API** | FastAPI 0.115+ (async) | REST API, file upload, SSE streaming |
| **Graph DB** | Neo4j 5.x + APOC | Knowledge Graph storage + Cypher queries |
| **Extraction** | LangExtract + Instructor | Grounded entity extraction |
| **Orchestration** | LangGraph 0.3+ | Multi-pass extraction + 17-node chat graph |
| **Embeddings** | VoyageAI (voyage-3.5) | Batch embedding pipeline |
| **Reranker** | zerank-1-small (local) | CrossEncoder reranking (sentence-transformers) |
| **NLI** | DeBERTa-v3-large (local) | Faithfulness checking |
| **Memory LLM** | Qwen3.5-4B (Ollama) | Conversation summarization |
| **Task Queue** | arq + Redis | Background extraction + embedding jobs |
| **Checkpointing** | PostgreSQL | LangGraph AsyncPostgresSaver + feedback store |
| **Monitoring** | LangFuse (self-hosted) | Traces, spans, cost tracking |
| **Logging** | structlog | Structured JSON logging |
| **Frontend** | Next.js 16 / React 19 | Chat UI, graph explorer, thread sidebar |
| **State Mgmt** | Zustand | Frontend state |
| **UI** | shadcn/ui + Tailwind | Component library |

### LLM Model Strategy

| Task | Model | Cost |
|------|-------|------|
| Entity extraction (Passes 1-4) | Gemini 2.5 Flash | ~$0.02/chapter |
| Entity reconciliation & dedup | GPT-4o-mini | ~$0.005/chapter |
| Chat generation | Gemini 2.5 Flash-Lite / DeepSeek V3.2 | ~$0.002/query |
| Conversation summarization | Qwen3.5-4B (local, Ollama) | $0 |
| Embeddings | VoyageAI voyage-3.5 | ~$0.001/chunk |
| Reranking | zerank-1-small (local) | $0 |
| NLI faithfulness | DeBERTa-v3-large (local) | $0 |

---

## Quick Start

### Prerequisites

- **Python 3.12+** (3.14 supported)
- **Node.js 20+** (for frontend)
- **Docker** (for infrastructure services)
- **uv** (recommended Python package manager): `pip install uv`
- **Ollama** (for local models): `https://ollama.ai`

### 1. Clone & Install

```bash
git clone https://github.com/xairon/WorldRAG.git
cd WorldRAG

# Install Python dependencies
uv sync --all-extras

# Install frontend dependencies
cd frontend && npm install && cd ..
```

### 2. Start Infrastructure

```bash
# Start Neo4j, Redis, PostgreSQL, LangFuse
docker compose up -d

# Wait for services to be healthy (~30s)
docker compose ps
```

Services available at:
| Service | URL | Credentials |
|---------|-----|-------------|
| Neo4j Browser | http://localhost:7474 | `neo4j` / `worldrag` |
| Neo4j Bolt | bolt://localhost:7687 | `neo4j` / `worldrag` |
| Redis | localhost:6379 | — |
| PostgreSQL | localhost:5432 | `worldrag` / `worldrag` |
| LangFuse | http://localhost:3001 | Create account on first visit |

### 3. Initialize Neo4j Schema

```bash
# Via cypher-shell (if installed)
cat scripts/init_neo4j.cypher | cypher-shell -u neo4j -p worldrag

# Or paste contents of scripts/init_neo4j.cypher into Neo4j Browser
```

### 4. Pull Local Models (Ollama)

```bash
ollama pull qwen2.5:4b       # Conversation summarization
# zerank-1-small and DeBERTa are loaded via sentence-transformers (auto-download)
```

### 5. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys (see Configuration section)
```

### 6. Start Backend

```bash
uv run uvicorn backend.app.main:app --reload --port 8000
```

API available at http://localhost:8000 — Swagger docs at http://localhost:8000/docs

### 7. Start Frontend

```bash
cd frontend && npm run dev
```

Frontend available at http://localhost:3000

### 8. Start arq Workers

```bash
# In a separate terminal — requires Redis + Neo4j running
uv run arq app.workers.settings.WorkerSettings
```

### 9. Upload & Process a Book

```bash
# Upload a book (ePub, PDF, or TXT)
curl -X POST http://localhost:8000/api/books \
  -F "file=@my_book.epub" \
  -F "title=The Primal Hunter" \
  -F "series_name=Primal Hunter" \
  -F "order_in_series=1" \
  -F "author=Zogarth" \
  -F "genre=litrpg"

# Response: { "book_id": "a1b2c3d4", "chapters_found": 42, ... }

# Trigger LLM extraction (async arq job)
curl -X POST http://localhost:8000/api/books/a1b2c3d4/extract

# Check stats
curl http://localhost:8000/api/books/a1b2c3d4/stats
```

---

## Pipeline Overview

```
Upload (epub/pdf/txt)
  -> Parse chapters (ingestion.py)
  -> Chunk chapters (chunking.py)
  -> Regex extract -- Pass 0 (regex_extractor.py)
  -> Store in Neo4j (book_repo.py)
  -> [Status: completed]

Extract (arq worker -- async)
  -> LangGraph: route -> [characters|systems|events|lore] (parallel fan-out)
  -> Reconcile in-graph (deduplicate all 10 entity types via LangGraph node)
  -> Apply alias_map normalization (names, owners, stat_changes)
  -> Persist entities to Neo4j (entity_repo.py -- 11 types)
  -> Create GROUNDED_IN relationships (label-aware UNWIND)
  -> DLQ for failed chapters
  -> [Status: extracted]
  -> Auto-enqueue embedding job

Embed (arq worker -- async)
  -> Fetch chunks without embeddings
  -> VoyageAI batch embed (128/batch)
  -> UNWIND write-back to Neo4j
  -> Cost tracking
  -> [Status: embedded]

Chat / Query
  -> POST /api/chat/{thread_id}/message
  -> 6-route intent classification
  -> HyDE + multi-query expansion
  -> Hybrid retrieve (vector + BM25 + RRF)
  -> CrossEncoder rerank (zerank-1-small)
  -> Cosine dedup (>80% threshold)
  -> Generate with CoT (analytical/timeline)
  -> NLI faithfulness check (DeBERTa-v3-large)
  -> Rewrite loop if faithfulness fails (max 2 retries)
  -> SSE stream tokens + sources
```

---

## Chat Pipeline Details

The chat agent is a ~17-node LangGraph graph with 6 adaptive routes.

### Intent Routes

| Route | When Used | Retrieval Strategy |
|-------|-----------|-------------------|
| `factual_lookup` | Direct fact queries ("What level is Jake?") | KG lookup first, fallback to hybrid RAG |
| `entity_qa` | Entity-centric questions ("Describe Jake's skills") | Hybrid RAG with entity filtering |
| `relationship_qa` | Relationship queries ("How do Jake and Milas know each other?") | KG path traversal + RAG |
| `timeline_qa` | Chronological questions ("What happened in Chapter 15?") | Temporal-sorted hybrid RAG |
| `analytical` | Complex reasoning ("Why did Jake choose X?") | Full hybrid RAG + CoT generation |
| `conversational` | Small talk, clarifications | Memory context only, no retrieval |

### Node Graph (17 nodes)

```
[classify_intent]
      |
      +--[conversational]--> [generate_conversational] --> [stream]
      |
      +--[factual_lookup / entity_qa / relationship_qa]
      |     |
      |  [kg_search] --> (found?) --yes--> [generate] --> [nli_check] --> [stream]
      |     |                    \                                  \
      |     |                     no                                 rewrite_loop
      |     v                      \
      +--[hyde_expand]              v
      |  [multi_query]         [hybrid_retrieve]
      |     |                       |
      +--[timeline_qa / analytical] |
            |                  [rerank]
         [hybrid_retrieve]         |
            |                  [dedup]
         [temporal_sort?]          |
            |               [generate (+CoT)]
         [rerank]                  |
            |                [nli_check]
         [dedup]                   |
            |                  [stream]
         [generate (+CoT)]
            |
         [nli_check]
            |
         [stream]
```

### Faithfulness Loop

After generation, `nli_check` scores the response against retrieved context using DeBERTa-v3-large. Thresholds are route-adaptive (analytical routes use lower thresholds than factual). If faithfulness fails, the pipeline rewrites the query and retries retrieval (max 2 retries before returning best attempt).

### Memory

Conversation history uses a sliding window of recent turns. Every 5 turns, Qwen3.5-4B (local, via Ollama) summarizes older turns into a compressed memory block. The summary + recent turns are injected into the generation prompt.

---

## API Reference

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Full health check (Neo4j, Redis, PostgreSQL, LangFuse) |
| `GET` | `/api/health/ready` | Quick readiness probe |

### Books

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/books` | Upload book file (ePub/PDF/TXT) + run ingestion pipeline |
| `GET` | `/api/books` | List all books |
| `GET` | `/api/books/{id}` | Get book details with chapter list |
| `GET` | `/api/books/{id}/stats` | Get book processing statistics |
| `POST` | `/api/books/{id}/extract` | Trigger LLM extraction pipeline (async arq job) |
| `DELETE` | `/api/books/{id}` | Delete book and all associated data |

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat/{thread_id}/message` | Send message, receive SSE stream (tokens + sources) |
| `GET` | `/api/chat/threads` | List conversation threads |
| `GET` | `/api/chat/{thread_id}/history` | Get full conversation history |
| `DELETE` | `/api/chat/{thread_id}` | Delete thread and checkpoint |
| `POST` | `/api/chat/feedback` | Submit thumbs up/down feedback |
| `GET` | `/api/chat/feedback/{message_id}` | Get feedback for a message |

### Graph Explorer

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/graph/{book_id}` | Get graph data (nodes + edges) for Sigma.js |
| `GET` | `/api/graph/{book_id}/entity/{entity_id}` | Get entity detail with relationships |
| `GET` | `/api/graph/{book_id}/search` | Search entities (fulltext + vector) |

### Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/admin/costs` | Cost tracking summary |
| `GET` | `/api/admin/dlq` | Dead letter queue contents |
| `POST` | `/api/admin/dlq/{id}/retry` | Retry failed extraction |

---

## Configuration

All configuration is via environment variables (`.env` file). See `.env.example` for all options.

### Essential Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `worldrag` | Neo4j password |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `DATABASE_URL` | `postgresql+asyncpg://worldrag:worldrag@localhost:5432/worldrag` | PostgreSQL URL |
| `OPENAI_API_KEY` | — | Required for reconciliation (GPT-4o-mini) |
| `GEMINI_API_KEY` | — | Required for extraction (Gemini Flash) |

### LLM Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGEXTRACT_MODEL` | `gemini-2.5-flash` | Model for entity extraction |
| `LLM_RECONCILIATION` | `openai:gpt-4o-mini` | Model for reconciliation |
| `LLM_CHAT` | `gemini:gemini-2.5-flash-lite` | Model for chat generation |
| `LLM_MEMORY` | `ollama:qwen2.5:4b` | Model for conversation summarization |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-zerank-1-small` | CrossEncoder model |
| `NLI_MODEL` | `cross-encoder/nli-deberta-v3-large` | NLI faithfulness model |

### Chat Pipeline

| Variable | Default | Description |
|----------|---------|-------------|
| `CHAT_MEMORY_WINDOW` | `10` | Number of recent turns in sliding window |
| `CHAT_SUMMARIZE_EVERY` | `5` | Summarize memory every N turns |
| `CHAT_MAX_REWRITE_RETRIES` | `2` | Max faithfulness rewrite retries |
| `CHAT_NLI_THRESHOLD_FACTUAL` | `0.7` | NLI pass threshold for factual routes |
| `CHAT_NLI_THRESHOLD_ANALYTICAL` | `0.5` | NLI pass threshold for analytical routes |
| `CHAT_RRF_K` | `60` | RRF fusion constant |
| `CHAT_TOP_K` | `20` | Documents to retrieve before reranking |
| `CHAT_RERANK_TOP_N` | `5` | Documents to keep after reranking |

### Cost Controls

| Variable | Default | Description |
|----------|---------|-------------|
| `COST_CEILING_PER_CHAPTER` | `0.50` | Max cost (USD) per chapter extraction |
| `COST_CEILING_PER_BOOK` | `50.00` | Max cost (USD) per book extraction |

### Monitoring

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGFUSE_HOST` | `http://localhost:3001` | LangFuse host URL |
| `LANGFUSE_PUBLIC_KEY` | — | LangFuse public key |
| `LANGFUSE_SECRET_KEY` | — | LangFuse secret key |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FORMAT` | `json` | Log format (`json` or `console`) |

---

## Ontology

WorldRAG uses a 3-layer ontology inspired by academic standards.

### Layer 1: Core Narrative (Universal)

Based on CIDOC-CRM, SEM, DOLCE, OntoMedia, FRBRoo/LRMoo:

```
Series --CONTAINS_WORK--> Book --HAS_CHAPTER--> Chapter --HAS_CHUNK--> Chunk
                                                                         |
Character --RELATES_TO--> Character                             GROUNDED_IN
Character --MEMBER_OF--> Faction                                     |
Character --PARTICIPATES_IN--> Event                                 v
Event --OCCURS_AT--> Location                             (source text offsets)
Event --CAUSES/ENABLES--> Event
Event --PART_OF--> Arc
Location --LOCATION_PART_OF--> Location
Character --POSSESSES--> Item
```

### Layer 2: LitRPG / Progression Fantasy

Genre-specific extensions:

```
Character --HAS_CLASS--> Class --EVOLVES_INTO--> Class
Character --HAS_SKILL--> Skill --SKILL_EVOLVES_INTO--> Skill
Character --HAS_TITLE--> Title
Character --AT_LEVEL--> Level
Character --IS_RACE--> Race
Skill --BELONGS_TO--> Class
Creature --INHABITS--> Location
```

### Layer 3: Series-Specific

Per-series customization (e.g., Primal Hunter: Bloodlines, Professions, Paths).

### Temporal Model

All mutable relationships carry temporal bounds:

```cypher
(jake:Character)-[:HAS_CLASS {
  valid_from_chapter: 1,
  valid_to_chapter: 42
}]->(hunter:Class {name: "Arcane Hunter"})
```

Query "What class did Jake have in Chapter 20?":
```cypher
MATCH (c:Character {name: "Jake"})-[r:HAS_CLASS]->(cls:Class)
WHERE r.valid_from_chapter <= 20
  AND (r.valid_to_chapter IS NULL OR r.valid_to_chapter >= 20)
RETURN cls.name
```

---

## Testing

### Run Tests

```bash
# All tests (810 tests)
uv run pytest backend/tests/ -v

# Fast tests only (exclude @slow)
uv run pytest backend/tests/ -v -m "not slow"

# With coverage report
uv run pytest backend/tests/ -v --cov=app --cov-report=term-missing

# Specific test file
uv run pytest backend/tests/test_chat_graph.py -v
```

### Linting

```bash
# Check
uv run ruff check backend/

# Auto-fix
uv run ruff check backend/ --fix

# Format
uv run ruff format backend/

# Type check
uv run pyright backend/
```

---

## Project Structure

```
WorldRAG/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app with lifespan management
│   │   ├── config.py               # Pydantic Settings (from .env)
│   │   ├── api/
│   │   │   ├── auth.py             # Authentication (require_auth)
│   │   │   ├── dependencies.py     # FastAPI Depends() -- Neo4j, Redis, etc.
│   │   │   ├── middleware.py       # Request context middleware
│   │   │   └── routes/
│   │   │       ├── health.py       # Health check endpoints
│   │   │       ├── books.py        # Book CRUD + ingestion + extraction
│   │   │       ├── chat.py         # Chat SSE + thread management + feedback
│   │   │       ├── graph.py        # Graph explorer API
│   │   │       └── admin.py        # Admin/monitoring endpoints
│   │   ├── core/
│   │   │   ├── logging.py          # structlog configuration
│   │   │   ├── resilience.py       # CircuitBreaker + retry_llm_call
│   │   │   ├── cost_tracker.py     # Token counting + cost tracking
│   │   │   ├── dead_letter.py      # Failed extraction DLQ (Redis)
│   │   │   ├── ontology_loader.py  # YAML ontology loader + enum validation
│   │   │   └── rate_limiter.py     # API rate limiting
│   │   ├── llm/
│   │   │   ├── providers.py        # Multi-provider LLM client factory
│   │   │   ├── embeddings.py       # VoyageAI embedding service
│   │   │   ├── reranker.py         # CrossEncoder reranking (zerank-1-small)
│   │   │   └── local_models.py     # Singleton loaders (NLI, reranker)
│   │   ├── schemas/
│   │   │   ├── book.py             # Book/Chapter/Chunk Pydantic models
│   │   │   ├── extraction.py       # 4-pass extraction result models
│   │   │   └── chat.py             # Chat message + feedback models
│   │   ├── repositories/
│   │   │   ├── base.py             # Neo4j base repository (read/write/batch)
│   │   │   ├── book_repo.py        # Book/Chapter/Chunk CRUD
│   │   │   ├── entity_repo.py      # Entity UPSERT (11 types)
│   │   │   └── chat_store.py       # PostgreSQL chat thread + feedback store
│   │   ├── services/
│   │   │   ├── ingestion.py        # ePub/PDF/TXT parser
│   │   │   ├── chunking.py         # Paragraph-aware text chunking
│   │   │   ├── deduplication.py    # 3-tier entity dedup
│   │   │   ├── graph_builder.py    # Orchestrator: Extract -> Reconcile -> Persist
│   │   │   ├── monitoring.py       # LangFuse integration helpers
│   │   │   └── extraction/
│   │   │       ├── regex_extractor.py  # Pass 0: 7 LitRPG regex patterns
│   │   │       ├── router.py           # Smart pass selection
│   │   │       ├── characters.py       # Pass 1: Character extraction
│   │   │       ├── systems.py          # Pass 2: System/progression extraction
│   │   │       ├── events.py           # Pass 3: Event extraction
│   │   │       ├── lore.py             # Pass 4: Lore extraction
│   │   │       └── reconciler.py       # Cross-pass entity reconciliation
│   │   ├── agents/
│   │   │   ├── extraction/         # LangGraph extraction graph
│   │   │   └── chat/               # LangGraph chat graph (17 nodes, 6 routes)
│   │   │       ├── graph.py        # build_chat_graph() entry point
│   │   │       ├── state.py        # ChatState TypedDict
│   │   │       ├── checkpointer.py # AsyncPostgresSaver setup
│   │   │       └── nodes/          # Individual LangGraph nodes
│   │   │           ├── router.py       # Intent classification (6 routes)
│   │   │           ├── hyde.py         # HyDE + multi-query expansion
│   │   │           ├── retrieve.py     # Hybrid retrieve (vector+BM25+RRF)
│   │   │           ├── rerank.py       # CrossEncoder reranking
│   │   │           ├── dedup.py        # Cosine similarity dedup
│   │   │           ├── kg_query.py     # KG direct lookup (kg_search)
│   │   │           ├── generate.py     # LLM generation + CoT
│   │   │           ├── nli_check.py    # DeBERTa-v3 faithfulness check
│   │   │           └── memory.py       # Sliding window + summarization
│   │   ├── prompts/
│   │   │   ├── extraction_characters.py  # Pass 1 LLM prompts
│   │   │   ├── extraction_systems.py     # Pass 2 LLM prompts
│   │   │   ├── extraction_events.py      # Pass 3 LLM prompts
│   │   │   ├── extraction_lore.py        # Pass 4 LLM prompts
│   │   │   └── chat_prompts.py           # Chat generation prompts
│   │   └── workers/
│   │       ├── settings.py         # arq WorkerSettings
│   │       ├── extraction_task.py  # Async extraction job
│   │       └── embedding_task.py   # Async embedding job
│   └── tests/                      # 810 tests
├── frontend/
│   ├── app/
│   │   ├── (reader)/
│   │   │   ├── books/              # Book list + upload
│   │   │   ├── graph/              # Sigma.js graph explorer
│   │   │   └── chat/               # Chat UI with thread sidebar
│   │   └── layout.tsx
│   ├── components/
│   │   ├── chat/                   # ChatInput, MessageList, SourcePanel, etc.
│   │   │   ├── thread-sidebar.tsx
│   │   │   ├── source-panel.tsx
│   │   │   ├── citation-highlight.tsx
│   │   │   ├── confidence-badge.tsx
│   │   │   └── feedback-buttons.tsx
│   │   └── graph/                  # Sigma.js wrapper components
│   ├── lib/
│   │   └── api.ts                  # apiFetch() + typed API clients
│   ├── hooks/                      # React hooks (useChat, useThread, etc.)
│   └── stores/                     # Zustand stores
├── ontology/
│   ├── core.yaml                   # Layer 1: Core narrative (CIDOC-CRM, SEM)
│   ├── litrpg.yaml                 # Layer 2: LitRPG progression (classes, skills)
│   └── primal_hunter.yaml          # Layer 3: Series-specific (Primal Hunter)
├── scripts/
│   ├── init_neo4j.cypher           # Neo4j schema: constraints, indexes, vectors
│   ├── migrations/                 # PostgreSQL Alembic migrations
│   └── seed_data/                  # Sample data for development
├── docs/
│   └── superpowers/                # Design specs + implementation plans
├── docker-compose.yml              # Neo4j + Redis + PostgreSQL + LangFuse
├── pyproject.toml                  # Python project config (uv/hatch)
├── .env.example                    # Environment variable template
└── CLAUDE.md                       # Claude Code instructions
```

---

## What's Implemented vs TODO

### Implemented (810 tests, all passing)

- [x] Full novel ingestion pipeline (ePub/PDF/TXT -> chapters -> chunks -> Neo4j)
- [x] Two-pass extraction: regex Pass 0 + LangGraph 4-pass LLM (11 entity types)
- [x] 3-tier entity deduplication (exact -> fuzzy -> embedding + LLM judge)
- [x] VoyageAI batch embedding pipeline (voyage-3.5)
- [x] arq async workers (extraction + embedding jobs, auto-chained)
- [x] Book ingestion + extraction + graph explorer APIs
- [x] Admin API (costs, DLQ, retry)
- [x] Ontology loader (3-layer YAML, enum validation)
- [x] Frontend: books list, Sigma.js graph explorer
- [x] Docker Compose infra (Neo4j, Redis, PostgreSQL, LangFuse)
- [x] SOTA Chat/RAG pipeline (LangGraph 17-node graph, 6 routes)
- [x] HyDE + multi-query expansion
- [x] Hybrid retrieval: vector (BGE-M3) + BM25 + RRF fusion
- [x] Local CrossEncoder reranker (zerank-1-small)
- [x] NLI faithfulness check (DeBERTa-v3-large) with rewrite loop
- [x] Conversation memory (sliding window + Qwen3.5-4B summarization)
- [x] PostgreSQL checkpointing (LangGraph AsyncPostgresSaver)
- [x] SSE streaming (token + source events)
- [x] Chat feedback API (PostgreSQL `chat_feedback` table)
- [x] Frontend chat UI (thread sidebar, source panel, citations, confidence badge, feedback)

### TODO / Remaining

- [ ] **Reader LangGraph agent**: Per-chapter summarization, highlight extraction, reading progress tracking
- [ ] **Frontend polish**: Mobile responsiveness, dark mode, graph filtering UI
- [ ] **Production deployment config**: Kubernetes manifests / Compose prod profile, TLS, secrets management
- [ ] **Series-level graph merging**: Cross-book entity resolution for multi-volume series
- [ ] **Graph validation**: Contradiction detection, temporal consistency checks
- [ ] **Wiki auto-generation**: Export KG to structured wiki format

---

## Key Commands

```bash
# Backend
uv run uvicorn backend.app.main:app --reload --port 8000
uv run pytest backend/tests/ -x -v
uv run ruff check backend/ --fix
uv run ruff format backend/
uv run pyright backend/

# arq worker (requires Redis + Neo4j running)
uv run arq app.workers.settings.WorkerSettings

# Frontend
cd frontend && npm run dev
cd frontend && npm run build

# Infrastructure
docker compose up -d          # Neo4j + Redis + PostgreSQL + LangFuse
docker compose down

# Neo4j Browser: http://localhost:7474 (neo4j/worldrag)
# LangFuse: http://localhost:3001
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>WorldRAG</strong> — Turning novels into knowledge, one chapter at a time.
</p>
