# Architecture

This document describes the complete system architecture of WorldRAG, from high-level system context down to internal component interactions.

## System Context

WorldRAG sits between end users and a constellation of external services. Users interact through a Next.js frontend that communicates with a FastAPI backend. The backend orchestrates LLM providers for entity extraction, a vector embedding service for semantic search, and a graph database for persistent storage.

```mermaid
graph TB
    User([End User])
    User -->|Browser| Frontend[Next.js 16 Frontend<br/>:3000]
    Frontend -->|REST API| Backend[FastAPI Backend<br/>:8000]

    Backend -->|Cypher / Bolt| Neo4j[(Neo4j 5<br/>Graph Database)]
    Backend -->|Task Queue| Redis[(Redis 7<br/>Queue + DLQ)]
    Backend -->|Checkpoints| PG[(PostgreSQL 16)]

    Backend -->|Extraction| OpenAI[OpenAI API]
    Backend -->|Extraction| Gemini[Google Gemini API]
    Backend -->|Extraction| Anthropic[Anthropic API]
    Backend -->|Embeddings| Voyage[Voyage AI API]
    Backend -->|Monitoring| LangFuse[LangFuse 2<br/>:3001]

    Redis --> Workers[arq Workers]
    Workers -->|Cypher| Neo4j
    Workers -->|LLM calls| OpenAI
    Workers -->|LLM calls| Gemini
    Workers -->|Embeddings| Voyage
```

## Container Diagram

The system is composed of six runtime containers plus external API services. All infrastructure runs in Docker; the application processes (backend, worker, frontend) run on the host during development.

```mermaid
graph TB
    subgraph "Docker Compose Infrastructure"
        Neo4j[(Neo4j 5<br/>:7474 / :7687<br/>APOC, 2G heap)]
        Redis[(Redis 7<br/>:6379<br/>password auth)]
        PG[(PostgreSQL 16<br/>:5432)]
        LangFuse[LangFuse 2<br/>:3001]
        LangFuseDB[(LangFuse DB<br/>PostgreSQL)]
        LangFuse --> LangFuseDB
    end

    subgraph "Application Processes"
        Backend[FastAPI Backend<br/>uvicorn :8000]
        Worker[arq Worker<br/>process_book_extraction<br/>process_book_embeddings]
        Frontend[Next.js Frontend<br/>:3000]
    end

    subgraph "External LLM APIs"
        OpenAI[OpenAI<br/>GPT-4o / GPT-4o-mini]
        Gemini[Google Gemini<br/>2.5 Flash]
        Voyage[Voyage AI<br/>voyage-3.5]
        Cohere[Cohere<br/>rerank-v3.5]
    end

    Frontend -->|HTTP /api proxy| Backend
    Backend -->|Bolt| Neo4j
    Backend -->|Redis protocol| Redis
    Backend -->|asyncpg| PG
    Backend -->|HTTP| LangFuse

    Worker -->|Bolt| Neo4j
    Worker -->|Redis protocol| Redis
    Worker -->|HTTP| OpenAI
    Worker -->|HTTP| Gemini
    Worker -->|HTTP| Voyage

    Backend -->|enqueue jobs| Redis
```

## Full Pipeline Flow

The processing pipeline has three phases: synchronous ingestion (during upload), asynchronous extraction (arq worker), and asynchronous embedding (arq worker, auto-chained).

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant API as FastAPI
    participant Ing as Ingestion
    participant Chk as Chunking
    participant Rgx as Regex Extractor
    participant Repo as BookRepository
    participant Q as Redis / arq
    participant W as Worker
    participant LG as LangGraph
    participant Rec as Reconciler
    participant ER as EntityRepository
    participant Emb as VoyageEmbedder

    User->>FE: Upload EPUB/PDF/TXT
    FE->>API: POST /api/books (multipart)

    rect rgb(230, 240, 255)
        Note over API,Repo: Phase 1 - Synchronous Ingestion
        API->>Ing: ingest_file(path)
        Ing-->>API: list[ChapterData]
        API->>Chk: chunk_chapter() per chapter
        Chk-->>API: list[ChunkData]
        API->>Rgx: extract() per chapter
        Rgx-->>API: list[RegexMatch]
        API->>Repo: create_book + create_chapters + create_chunks + store_regex_matches
    end

    API-->>FE: IngestionResult (status: completed)

    User->>FE: Click "Extract"
    FE->>API: POST /api/books/{id}/extract
    API->>Q: enqueue(process_book_extraction)
    API-->>FE: JobEnqueuedResult

    rect rgb(255, 240, 230)
        Note over W,ER: Phase 2 - Async Extraction (per chapter)
        Q->>W: process_book_extraction
        W->>LG: extract_chapter(text, genre)
        LG->>LG: route -> fan-out [chars|sys|evt|lore]
        LG->>LG: merge results
        LG->>LG: reconcile (dedup all 10 entity types)
        LG-->>W: ChapterExtractionResult + alias_map
        W->>W: apply alias_map normalization
        W->>ER: upsert_extraction_result (13 methods)
        W->>ER: store_grounding (GROUNDED_IN rels)
    end

    rect rgb(230, 255, 230)
        Note over W,Emb: Phase 3 - Async Embedding (auto-chained)
        W->>Q: enqueue(process_book_embeddings)
        Q->>W: process_book_embeddings
        W->>Repo: get_chunks_for_embedding
        W->>Emb: embed_texts (batch 128)
        Emb-->>W: list[list[float]]
        W->>Repo: UNWIND write embeddings to Neo4j
    end
```

## LangGraph Extraction Graph

Each chapter is processed through a LangGraph `StateGraph` that parallelizes extraction across four specialized passes. The router analyzes chapter content via keyword detection and dispatches only the relevant passes using LangGraph's `Send()` API for native parallel fan-out.

```mermaid
flowchart LR
    START([START]) --> Route[route_extraction_passes]

    Route -->|"Send('characters', state)"| P1[Pass 1<br/>Characters &<br/>Relationships]
    Route -->|"Send('systems', state)<br/>if system_keywords >= 3"| P2[Pass 2<br/>Systems &<br/>Progression]
    Route -->|"Send('events', state)<br/>if event_keywords >= 2"| P3[Pass 3<br/>Events &<br/>Timeline]
    Route -->|"Send('lore', state)<br/>if lore_keywords >= 3"| P4[Pass 4<br/>Lore &<br/>Worldbuilding]

    P1 --> Merge[merge_results]
    P2 --> Merge
    P3 --> Merge
    P4 --> Merge
    Merge --> Reconcile[reconcile_in_graph]
    Reconcile --> END([END])

    style P1 fill:#4A90D9,color:#fff
    style P2 fill:#7B68EE,color:#fff
    style P3 fill:#E8853D,color:#fff
    style P4 fill:#50C878,color:#fff
    style Reconcile fill:#50C878,color:#fff
```

**State management**: The `ExtractionPipelineState` TypedDict carries 18 fields. Three fields use `operator.add` reducers (`grounded_entities`, `passes_completed`, `errors`) so that parallel branches automatically merge their lists when converging at the `merge` node. The `alias_map` field carries the reconciliation output (entity name deduplication) from the `reconcile` node through to the final result.

**Routing rules**:
- Pass 1 (Characters): **always runs** -- characters appear in every chapter
- Pass 2 (Systems): runs when `system_keywords >= 3`, or genre is LitRPG and `system_keywords >= 1`, or regex matches exist
- Pass 3 (Events): runs when `event_keywords >= 2`
- Pass 4 (Lore): runs when `lore_keywords >= 3`
- Short chapters (< 2000 chars): all passes run unconditionally

## Repository Pattern

All Neo4j access goes through typed repository classes. Services never execute Cypher directly -- they call repository methods that handle session management, parameterization, and error handling.

**`Neo4jRepository`** (base class):
- `execute_read(query, params)` -- read transaction
- `execute_write(query, params)` -- write transaction
- `count(label)`, `exists(label, prop, value)`

**`BookRepository`** (14 methods): CRUD for books, chapters, chunks, regex matches. Manages the bibliographic layer (Series -> Book -> Chapter -> Chunk).

**`EntityRepository`** (13 upsert + 1 orchestrator): Handles all Knowledge Graph entities. The `upsert_extraction_result()` orchestrator executes in three phases:
1. **Sequential**: Characters, then Relationships (relationships reference characters)
2. **Parallel** (`asyncio.gather`): Skills, Classes, Titles, LevelChanges, StatChanges, Events, Locations, Items, Creatures, Factions, Concepts
3. **Sequential**: Grounding data

Every write carries a `batch_id` UUID for rollback capability.

## Worker Architecture

Background processing uses arq (async Redis queue) with two task functions that chain automatically. The worker process maintains its own Neo4j driver, Redis client, cost tracker, and dead letter queue -- independent from the FastAPI process.

```mermaid
flowchart LR
    API[POST /books/id/extract] -->|enqueue| Redis{Redis<br/>worldrag:arq}
    Redis -->|dequeue| Extract[process_book_extraction<br/>LangGraph pipeline<br/>per chapter]
    Extract -->|auto-enqueue| Embed[process_book_embeddings<br/>Voyage AI batch<br/>128 chunks/call]
    Extract -->|failures| DLQ[(Dead Letter Queue<br/>Redis list)]
    Embed -->|write vectors| Neo4j[(Neo4j)]
    Extract -->|write entities| Neo4j

    style Extract fill:#E8853D,color:#fff
    style Embed fill:#50C878,color:#fff
    style DLQ fill:#DC3545,color:#fff
```

**Job lifecycle**:
- Deterministic job IDs: `extract:{book_id}`, `embed:{book_id}` (idempotent enqueue)
- Job status polling via `GET /api/books/{id}/jobs`
- Worker startup initializes Neo4j, Redis, CostTracker, DeadLetterQueue
- Worker shutdown cleanly closes all connections

**Configuration** (from `config.py`):
- `arq_max_jobs`: 5 concurrent jobs
- `arq_job_timeout`: 3600s (1 hour per job)
- `arq_keep_result`: 86400s (24 hours)

## Frontend Architecture

The frontend is a Next.js 16 application using the App Router pattern with Server Components by default. Client-side interactivity is limited to the graph visualization and form interactions.

```mermaid
graph TB
    subgraph "Next.js App Router"
        Layout[RootLayout<br/>Sidebar Navigation]
        Layout --> Home[/ Dashboard<br/>Stats + Health]
        Layout --> Books[/books<br/>Upload + List + Extract]
        Layout --> Graph[/graph<br/>D3 Force Graph Explorer]
        Layout --> Chat[/chat<br/>Placeholder]
    end

    subgraph "Components"
        NavLink[NavLink<br/>Active route detection]
        ForceGraph[ForceGraph<br/>react-force-graph-2d<br/>Color-coded by entity type]
    end

    subgraph "API Client lib/api.ts"
        Fetch[Typed fetch functions<br/>20 endpoint wrappers]
    end

    Graph --> ForceGraph
    Layout --> NavLink
    Books --> Fetch
    Graph --> Fetch
    Home --> Fetch
```

**Graph Explorer features**:
- Book selector and entity type filter
- Full-text entity search
- Subgraph loading per book with chapter filtering
- Node color coding: Character (blue), Skill (green), Class (purple), Event (orange), Location (cyan), etc.
- Click-to-inspect entity details and character profiles

## Resilience Patterns

Every external service call is protected by a layered resilience stack: rate limiting, circuit breaking, and retry with exponential backoff.

```mermaid
stateDiagram-v2
    [*] --> CLOSED: Initial state
    CLOSED --> OPEN: failure_count >= threshold (5)
    OPEN --> HALF_OPEN: recovery_timeout elapsed (60s)
    HALF_OPEN --> CLOSED: success_count >= max_calls (3)
    HALF_OPEN --> OPEN: Any failure

    note right of CLOSED: All requests pass through
    note right of OPEN: All requests fail immediately
    note right of HALF_OPEN: Limited requests allowed
```

**Three layers of protection**:

| Layer | Implementation | Purpose |
|-------|---------------|---------|
| Rate limiter | `ProviderRateLimiter` (aiolimiter + Semaphore) | Prevent hitting API rate limits |
| Circuit breaker | Custom `CircuitBreaker` (asyncio.Lock) | Stop cascading failures |
| Retry | `@retry_llm_call` (tenacity, exponential + jitter) | Handle transient errors |

**Per-provider configuration**:

| Provider | Rate (RPM) | Concurrency | Circuit breaker |
|----------|-----------|-------------|----------------|
| OpenAI | 200 | 20 | `openai_breaker` |
| Gemini | 500 | 20 | `gemini_breaker` |
| Anthropic | 40 | 10 | `anthropic_breaker` |
| Voyage AI | 200 | 15 | `voyage_breaker` |
| Cohere | 80 | 10 | `cohere_breaker` |

**Dead Letter Queue**: Failed chapter extractions are pushed to a Redis-backed DLQ (`DeadLetterQueue`) with metadata (book_id, chapter, error_type, timestamp, attempt_count). Entries can be inspected via `GET /api/admin/dlq`, cleared via `POST /api/admin/dlq/clear`, retried individually via `POST /api/admin/dlq/retry/{book_id}/{chapter}`, or bulk-retried via `POST /api/admin/dlq/retry-all`.

## Cross-Cutting Concerns

### Structured Logging

All logging uses `structlog` with JSON output in production and colored console output in development. Context variables are automatically bound to every log entry:

| Context Variable | Source | Purpose |
|-----------------|--------|---------|
| `request_id` | `RequestContextMiddleware` | Correlate logs for a single HTTP request |
| `book_id` | Set by services | Filter logs per book |
| `chapter` | Set by extraction passes | Filter logs per chapter |
| `pipeline_stage` | Set by graph builder | Track pipeline progress |

### Cost Tracking

The `CostTracker` records every LLM API call with model, provider, token counts, and computed cost. It enforces configurable ceilings per chapter (`$0.50` default) and per book (`$50.00` default) to prevent runaway costs.

Pre-configured pricing for 8 models: GPT-4o, GPT-4o-mini, Gemini 2.5 Flash, Gemini 2.0 Flash, Claude 3.5 Sonnet, Claude 3.5 Haiku, Voyage 3.5, Cohere Rerank v3.5.

### Authentication

Two-tier authentication via Bearer tokens:
- **User endpoints** (`require_auth`): validated against `WORLDRAG_API_KEY`
- **Admin endpoints** (`require_admin`): validated against `WORLDRAG_ADMIN_API_KEY`
- **Dev mode**: when keys are empty, all requests pass through (no auth required)

---

**Next**: [Technology Stack](./tech-stack.md) for the rationale behind every technology choice.
