<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-blue?logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Neo4j-5.x-008CC1?logo=neo4j&logoColor=white" alt="Neo4j">
  <img src="https://img.shields.io/badge/Next.js-15-000000?logo=next.js&logoColor=white" alt="Next.js 15">
  <img src="https://img.shields.io/badge/LangGraph-0.3+-1C3C3C?logo=langchain&logoColor=white" alt="LangGraph">
  <img src="https://img.shields.io/badge/Tests-119%20passing-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

# WorldRAG

**SOTA Knowledge Graph construction system for fiction novel universes.**

Transform novels (LitRPG, fantasy, sci-fi) into rich, queryable Knowledge Graphs. WorldRAG extracts characters, relationships, skills, events, locations, and lore from books — then builds a temporally-aware Neo4j graph that evolves chapter by chapter.

> Built for series like *The Primal Hunter*, *Defiance of the Fall*, *He Who Fights With Monsters* — but works with any fiction genre.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Extraction Pipeline](#extraction-pipeline)
- [Ontology](#ontology)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Roadmap](#roadmap)
- [Contributing](#contributing)

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

### Infrastructure

- **Cost optimization**: Model tiering (Gemini Flash for extraction, GPT-4o-mini for reconciliation), per-chapter cost ceilings
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
              ┌──────────┼──────────────┐
              |          |              |
         [Characters] [Systems]   [Events] [Lore]    (Passes 1-4 — LLM)
              |          |              |
              └──────────┼──────────────┘
                         |
                 [Reconciliation]
                  Dedup + Aliases
                         |
                    [Neo4j KG]
                  ╔═══════════╗
                  ║ Characters ║──RELATES_TO──▶ Characters
                  ║   Skills   ║──HAS_SKILL──▶ Characters
                  ║   Events   ║──PARTICIPATES──▶ Characters
                  ║ Locations  ║──OCCURS_AT──▶ Events
                  ║   Items    ║──POSSESSES──▶ Characters
                  ╚═══════════╝
```

### Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **API** | FastAPI (async) | REST API, file upload, SSE |
| **Graph DB** | Neo4j 5.x + APOC | Knowledge Graph storage |
| **Extraction** | LangExtract + Instructor | Grounded entity extraction |
| **Orchestration** | LangGraph | Multi-pass extraction pipeline |
| **Embeddings** | Voyage AI (voyage-3.5) | Semantic search |
| **Reranking** | Cohere | Hybrid retrieval reranking |
| **Task Queue** | arq + Redis | Background processing |
| **Checkpointing** | PostgreSQL | LangGraph state persistence |
| **Monitoring** | LangFuse (self-hosted) | Traces, cost tracking |
| **Logging** | structlog | Structured JSON logging |
| **Frontend** | Next.js 15 / React 19 | Dashboard, Graph Explorer, Chat |

### LLM Model Strategy

| Task | Model | Cost |
|------|-------|------|
| Entity extraction (Passes 1-4) | Gemini 2.5 Flash | ~$0.02/chapter |
| Entity reconciliation & dedup | GPT-4o-mini | ~$0.005/chapter |
| Classification & Cypher gen | GPT-4o-mini | ~$0.002/query |
| User-facing chat | GPT-4o | ~$0.01/query |
| Embeddings | Voyage 3.5 | ~$0.001/chunk |

---

## Quick Start

### Prerequisites

- **Python 3.12+** (3.14 supported)
- **Node.js 20+** (for frontend)
- **Docker** (for infrastructure services)
- **uv** (recommended Python package manager): `pip install uv`

### 1. Clone & Install

```bash
git clone https://github.com/xairon/WorldRAG.git
cd WorldRAG

# Install Python dependencies
uv sync --all-extras

# Install frontend dependencies (when available)
# cd frontend && npm install
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

This creates:
- 12 uniqueness constraints (Character, Skill, Class, Location, etc.)
- 15+ property indexes (for lookup and temporal queries)
- 8 fulltext indexes (for keyword search)
- 1 vector index (for semantic search with Voyage embeddings)
- 7 relationship indexes (for temporal queries on progression)

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys:
# - OPENAI_API_KEY (required for reconciliation)
# - GEMINI_API_KEY (required for extraction)
# - VOYAGE_API_KEY (optional, for embeddings)
# - COHERE_API_KEY (optional, for reranking)
```

### 5. Start Backend

```bash
uv run uvicorn backend.app.main:app --reload --port 8000
```

API available at http://localhost:8000 — Swagger docs at http://localhost:8000/docs

### 6. Upload & Process a Book

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

# Trigger LLM extraction (expensive step)
curl -X POST http://localhost:8000/api/books/a1b2c3d4/extract

# Check stats
curl http://localhost:8000/api/books/a1b2c3d4/stats
```

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
| `OPENAI_API_KEY` | — | Required for reconciliation (GPT-4o-mini) |
| `GEMINI_API_KEY` | — | Required for extraction (Gemini Flash) |

### LLM Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGEXTRACT_MODEL` | `gemini-2.5-flash` | Model for entity extraction |
| `LANGEXTRACT_PASSES` | `2` | Number of extraction passes |
| `LLM_RECONCILIATION` | `openai:gpt-4o-mini` | Model for reconciliation |
| `LLM_CHAT` | `openai:gpt-4o` | Model for user-facing chat |
| `USE_BATCH_API` | `true` | Use OpenAI Batch API for cost savings |

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
| `POST` | `/api/books/{id}/extract` | Trigger LLM extraction pipeline |
| `DELETE` | `/api/books/{id}` | Delete book and all associated data |

### Book Upload (`POST /api/books`)

**Parameters** (multipart form):
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | File | Yes | Book file (.epub, .pdf, .txt) |
| `title` | string | No | Book title (defaults to filename) |
| `series_name` | string | No | Series name for grouping |
| `order_in_series` | int | No | Position in series |
| `author` | string | No | Author name |
| `genre` | string | No | Genre (default: `litrpg`) |

**Response** (`IngestionResult`):
```json
{
  "book_id": "a1b2c3d4",
  "title": "The Primal Hunter",
  "chapters_found": 42,
  "chunks_created": 380,
  "regex_matches_total": 156,
  "status": "completed"
}
```

### Extraction (`POST /api/books/{id}/extract`)

Triggers the full 4-pass LLM extraction + reconciliation pipeline. Requires book status to be `completed` (ingested) first.

**Response** (`ExtractionResult`):
```json
{
  "book_id": "a1b2c3d4",
  "chapters_processed": 42,
  "chapters_failed": 0,
  "failed_chapters": [],
  "total_entities": 1247,
  "status": "extracted"
}
```

---

## Extraction Pipeline

### Pipeline Overview

```
Book File  ──▶  Ingestion  ──▶  Chunking  ──▶  Regex (Pass 0)  ──▶  LLM Passes (1-4)  ──▶  Reconciliation  ──▶  Neo4j
```

### Pass 0: Regex Extraction (Free)

Pre-extracts structured data from blue boxes and system notifications using 7 regex patterns:

| Pattern | Example | Captures |
|---------|---------|----------|
| `skill_acquired` | `[Skill Acquired: Mana Sense - Common]` | name, rank |
| `level_up` | `Level: 87 -> 88` | old_value, new_value |
| `class_obtained` | `Class: Arcane Hunter (Legendary)` | name, tier_info |
| `title_earned` | `Title earned: Hydra Slayer` | name |
| `stat_increase` | `+5 Perception` | value, stat_name |
| `evolution` | `Evolution -> Transcendent Viper` | target |
| `blue_box_generic` | `[Any bracketed text]` | content |

Specific patterns run first; the generic blue box pattern only captures unmatched spans (overlap deduplication via `seen_spans`).

### Pass 1-4: LLM Extraction (Smart Routing)

The **Router** analyzes chapter content and only activates relevant passes:

| Pass | Always Runs? | Trigger Keywords |
|------|-------------|------------------|
| **Characters** | Yes | Always included |
| **Systems** | LitRPG: 1 keyword | `skill`, `level`, `class`, `title`, `stat`, `ability`, `evolution` |
| **Events** | 2+ keywords | `battle`, `fight`, `quest`, `died`, `killed`, `betrayed`, `revealed` |
| **Lore** | 3+ keywords | `dungeon`, `city`, `kingdom`, `artifact`, `prophecy`, `ancient` |

For chapters < 2000 characters, all passes run regardless (short chapters are cheap).

### Entity Reconciliation

After extraction, a 3-tier deduplication pipeline resolves entity conflicts:

1. **Exact match** (free, instant): Normalize names (lowercase, strip articles `The`/`A`/`An`)
2. **Fuzzy match** (free, fast): thefuzz ratio scoring
   - Score >= 95: auto-merge
   - Score 85-94: candidate for LLM review
   - Score < 85: different entities
3. **LLM-as-Judge** (Instructor): Resolves ambiguous fuzzy pairs with semantic understanding

Result: unified `alias_map` applied to all entity references across all passes.

---

## Ontology

WorldRAG uses a 3-layer ontology inspired by academic standards:

### Layer 1: Core Narrative (Universal)

Based on CIDOC-CRM, SEM, DOLCE, OntoMedia, FRBRoo/LRMoo:

```
Series ──CONTAINS_WORK──▶ Book ──HAS_CHAPTER──▶ Chapter ──HAS_CHUNK──▶ Chunk
                                                                          |
Character ──RELATES_TO──▶ Character                              GROUNDED_IN
Character ──MEMBER_OF──▶ Faction                                      |
Character ──PARTICIPATES_IN──▶ Event                                  ▼
Event ──OCCURS_AT──▶ Location                               (source text offsets)
Event ──CAUSES/ENABLES──▶ Event
Event ──PART_OF──▶ Arc
Location ──LOCATION_PART_OF──▶ Location
Character ──POSSESSES──▶ Item
```

### Layer 2: LitRPG / Progression Fantasy

Genre-specific extensions:

```
Character ──HAS_CLASS──▶ Class ──EVOLVES_INTO──▶ Class
Character ──HAS_SKILL──▶ Skill ──SKILL_EVOLVES_INTO──▶ Skill
Character ──HAS_TITLE──▶ Title
Character ──AT_LEVEL──▶ Level
Character ──IS_RACE──▶ Race
Skill ──BELONGS_TO──▶ Class
Creature ──INHABITS──▶ Location
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
# All tests (119 tests, ~19s)
uv run pytest backend/tests/ -v

# Fast tests only (exclude @slow)
uv run pytest backend/tests/ -v -m "not slow"

# With coverage report
uv run pytest backend/tests/ -v --cov=app --cov-report=term-missing

# Specific test file
uv run pytest backend/tests/test_chunking.py -v
```

### Test Suite Overview

| File | Tests | Coverage |
|------|-------|----------|
| `test_cost_tracker.py` | 15 | Token counting, model pricing, cost tracking |
| `test_regex_extractor.py` | 12 | 7 LitRPG regex patterns, dedup, offset validation |
| `test_deduplication.py` | 25 | 3-tier entity dedup (exact, fuzzy, LLM) |
| `test_router.py` | 14 | Smart pass selection, genre thresholds |
| `test_ingestion.py` | 14 | Chapter parsing, TXT format, boundary detection |
| `test_chunking.py` | 16 | Paragraph splitting, overlap, sentence splitting |
| `test_base_repository.py` | 6 | Neo4j CRUD operations (mocked) |
| `test_resilience.py` | 13 | Circuit breaker FSM, retry patterns |
| **Total** | **119** | |

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
│   │   │   ├── dependencies.py     # FastAPI Depends() — Neo4j, Redis, etc.
│   │   │   ├── middleware.py       # Request context middleware
│   │   │   └── routes/
│   │   │       ├── health.py       # Health check endpoints
│   │   │       ├── books.py        # Book CRUD + ingestion + extraction
│   │   │       └── admin.py        # Admin/monitoring endpoints
│   │   ├── core/
│   │   │   ├── logging.py          # structlog configuration
│   │   │   ├── resilience.py       # CircuitBreaker + retry_llm_call
│   │   │   ├── cost_tracker.py     # Token counting + cost tracking
│   │   │   ├── dead_letter.py      # Failed extraction DLQ (Redis)
│   │   │   └── rate_limiter.py     # API rate limiting
│   │   ├── llm/
│   │   │   ├── providers.py        # Multi-provider LLM client factory
│   │   │   ├── embeddings.py       # Voyage AI embedding service
│   │   │   └── reranker.py         # Cohere reranking service
│   │   ├── schemas/
│   │   │   ├── book.py             # Book/Chapter/Chunk Pydantic models
│   │   │   └── extraction.py       # 4-pass extraction result models
│   │   ├── repositories/
│   │   │   ├── base.py             # Neo4j base repository (read/write/batch)
│   │   │   ├── book_repo.py        # Book/Chapter/Chunk CRUD
│   │   │   └── entity_repo.py      # Entity UPSERT (Characters, Skills, etc.)
│   │   ├── services/
│   │   │   ├── ingestion.py        # ePub/PDF/TXT parser
│   │   │   ├── chunking.py         # Paragraph-aware text chunking
│   │   │   ├── deduplication.py    # 3-tier entity dedup
│   │   │   ├── graph_builder.py    # Orchestrator: Extract → Reconcile → Persist
│   │   │   ├── monitoring.py       # LangFuse integration helpers
│   │   │   └── extraction/
│   │   │       ├── regex_extractor.py  # Pass 0: 7 LitRPG regex patterns
│   │   │       ├── router.py          # Smart pass selection
│   │   │       ├── characters.py      # Pass 1: Character extraction
│   │   │       ├── systems.py         # Pass 2: System/progression extraction
│   │   │       ├── events.py          # Pass 3: Event extraction
│   │   │       ├── lore.py            # Pass 4: Lore extraction
│   │   │       └── reconciler.py      # Cross-pass entity reconciliation
│   │   ├── prompts/
│   │   │   ├── extraction_characters.py  # Pass 1 LLM prompts
│   │   │   ├── extraction_systems.py     # Pass 2 LLM prompts
│   │   │   ├── extraction_events.py      # Pass 3 LLM prompts
│   │   │   └── extraction_lore.py        # Pass 4 LLM prompts
│   │   └── agents/
│   │       └── state.py            # LangGraph state definitions
│   └── tests/                      # 119 tests (see Testing section)
├── ontology/
│   ├── core.yaml                   # Layer 1: Core narrative (CIDOC-CRM, SEM)
│   ├── litrpg.yaml                 # Layer 2: LitRPG progression (classes, skills)
│   └── primal_hunter.yaml          # Layer 3: Series-specific (Primal Hunter)
├── scripts/
│   └── init_neo4j.cypher           # Neo4j schema: constraints, indexes, vectors
├── docker-compose.yml              # Neo4j + Redis + PostgreSQL + LangFuse
├── pyproject.toml                  # Python project config (uv/hatch)
├── .env.example                    # Environment variable template
└── CLAUDE.md                       # Claude Code instructions
```

---

## Roadmap

### Completed

- [x] **Phase 1**: Infrastructure (FastAPI, Neo4j, Redis, PostgreSQL, LangFuse, Docker)
- [x] **Phase 2a**: Ingestion & chunking (ePub, PDF, TXT parsing, paragraph-aware chunking)
- [x] **Phase 2b**: 4-pass LLM extraction (Characters, Systems, Events, Lore via LangGraph)
- [x] **Phase 2c**: Reconciliation & entity resolution (3-tier dedup, alias mapping)
- [x] **Phase 2d**: Test suite (119 tests, full backend coverage)

### In Progress

- [ ] **Phase 3**: Use cases — RAG query pipeline (hybrid retrieval + LLM)
- [ ] **Phase 5**: Frontend — Next.js dashboard, graph explorer, chat interface

### Planned

- [ ] **Phase 4**: Embeddings & vector search (Voyage AI, Neo4j vector index)
- [ ] **Phase 6**: Series-level graph merging (cross-book entity resolution)
- [ ] **Phase 7**: Graph validation & contradiction detection
- [ ] **Phase 8**: Wiki auto-generation from KG

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests: `uv run pytest backend/tests/ -v`
4. Run linter: `uv run ruff check backend/ --fix`
5. Commit changes
6. Push to branch and open a Pull Request

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>WorldRAG</strong> — Turning novels into knowledge, one chapter at a time.
</p>
