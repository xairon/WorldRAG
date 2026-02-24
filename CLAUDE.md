# WorldRAG — Claude Code Instructions

## Project Overview

WorldRAG is a SOTA Knowledge Graph construction system for fiction novel universes (LitRPG, fantasy, sci-fi). It extracts entities, relationships, events, and temporal data from novels and builds a rich, evolving Neo4j Knowledge Graph.

**Priority**: KG construction quality is #1. Use cases (reader, chat, wiki) come after.

## Architecture

- **Backend**: Python 3.12+ / FastAPI (async everywhere)
- **Frontend**: Next.js 16 / React 19 / TypeScript
- **Graph DB**: Neo4j 5.x (direct Cypher, no ORM)
- **Extraction**: LangExtract (grounded) + Instructor (reconciliation)
- **Orchestration**: LangGraph (3 separate graphs: extraction, reader, chat)
- **Monitoring**: LangFuse (self-hosted) + structlog
- **Task Queue**: arq + Redis
- **Embeddings**: Local BGE-M3 (default, GPU) or VoyageAI (optional API)
- **Reranker**: Cohere (rerank-v3.5) — built, not yet wired to query
- **Checkpointing**: PostgreSQL (LangGraph AsyncPostgresSaver) — connected, not yet used

## Key Commands

```bash
# Backend
python -m uv run uvicorn backend.app.main:app --reload --port 8000
python -m uv run pytest backend/tests/ -x -v
python -m uv run ruff check backend/ --fix
python -m uv run ruff format backend/
python -m uv run pyright backend/

# arq worker (requires Redis + Neo4j running)
python -m uv run arq app.workers.settings.WorkerSettings

# Frontend
cd frontend && npm run dev
cd frontend && npm run build

# Infrastructure
docker compose up -d          # Neo4j + Redis + PostgreSQL + LangFuse
docker compose down

# Neo4j Browser: http://localhost:7474 (neo4j/worldrag)
# LangFuse: http://localhost:3001
```

## Code Conventions

### Python (backend/)
- Python 3.12+, async/await everywhere
- Pydantic v2 for all data models (BaseModel, not dataclass)
- Type hints mandatory (pyright standard mode)
- Absolute imports: `from app.core.logging import get_logger`
- All DB operations via repositories (app/repositories/)
- All LLM calls wrapped with LangFuse tracing
- structlog for logging (never print())
- Error handling: tenacity for retries, circuit breaker for providers
- Never log `error=str(e)` in exception handlers — use `exc_info=True` or `type(e).__name__`

### TypeScript (frontend/)
- TypeScript strict mode
- Next.js 16 App Router (not Pages)
- Tailwind CSS + shadcn/ui components
- Server Components by default, 'use client' only when needed

### Neo4j / Cypher
- MERGE with uniqueness constraints (never CREATE for entities)
- All temporal relations carry valid_from_chapter / valid_to_chapter
- batch_id UUID on every write (for rollback)
- Parameterized queries only ($param, never string interpolation)

## Project Structure

```
WorldRAG/
├── backend/app/          # FastAPI backend
│   ├── api/              # Routes + middleware + auth + dependencies
│   ├── core/             # Logging, resilience, rate limiting, cost tracking, DLQ
│   ├── llm/              # LLM providers, embeddings (local BGE-M3 or Voyage), reranker (Cohere)
│   ├── schemas/          # Pydantic models
│   ├── repositories/     # Neo4j data access (base, book_repo, entity_repo)
│   ├── services/         # Business logic + extraction pipeline + embedding
│   ├── agents/           # LangGraph graphs (extraction done; reader, chat TODO)
│   ├── prompts/          # LLM prompt templates
│   └── workers/          # arq task queue (extraction + embedding tasks)
├── frontend/             # Next.js frontend (app/, lib/, components/)
├── ontology/             # YAML ontology definitions (core, genre, series)
├── scripts/              # Neo4j init, migrations, seed data
└── docker-compose.yml    # Infrastructure (Neo4j, Redis, PostgreSQL, LangFuse)
```

## Ontology Layers

1. **Layer 1 (Core)**: Universal narrative entities (Character, Event, Location, Item, Arc)
2. **Layer 2 (Genre)**: LitRPG-specific (Class, Skill, Level, System, Title)
3. **Layer 3 (Series)**: Per-series config (Bloodline, Profession, etc.)

Defined in `ontology/*.yaml`, enforced via Cypher constraints in `scripts/init_neo4j.cypher`.
Loaded at runtime by `OntologyLoader` (app/core/ontology_loader.py) with enum validation.

## Important Patterns

- **Two-pass extraction**: Regex (Passe 0) for blue boxes/stats → LLM (Passes 1-4) for narrative
- **Entity resolution**: Exact match → Fuzzy (thefuzz) → Embedding similarity + LLM-as-Judge
- **Temporality**: Chapter-based (valid_from_chapter/valid_to_chapter), not datetime
- **Source grounding**: Every entity links back to its source chunk with char offsets
- **Cost optimization**: Gemini 2.5 Flash for extraction + reconciliation (single API key)
- **Async workers**: POST /books/{id}/extract enqueues arq job, auto-chains embedding on completion
- **Fulltext search**: entity_fulltext Neo4j index with Lucene escaping + CONTAINS fallback

## Pipeline Flow

```
Upload (epub/pdf/txt)
  → Parse chapters (ingestion.py)
  → Chunk chapters (chunking.py)
  → Regex extract — Passe 0 (regex_extractor.py)
  → Store in Neo4j (book_repo.py)
  → [Status: completed]

Extract (arq worker — async)
  → LangGraph: route → [characters|systems|events|lore] (parallel fan-out)
  → Reconcile in-graph (deduplicate all 10 entity types via LangGraph node)
  → Apply alias_map normalization (names, owners, stat_changes)
  → Persist entities to Neo4j (entity_repo.py — 11 types)
  → Create GROUNDED_IN relationships (label-aware UNWIND)
  → DLQ for failed chapters
  → [Status: extracted]
  → Auto-enqueue embedding job

Embed (arq worker — async)
  → Fetch chunks without embeddings
  → Local BGE-M3 batch embed (128/batch, GPU) or VoyageAI API
  → UNWIND write-back to Neo4j
  → Cost tracking (local = free)
  → [Status: embedded]
```

## Implementation Status

### ✅ Complete
- Extraction pipeline (LangGraph, 4 parallel passes)
- Regex extractor (Passe 0 — blue boxes, level-ups, skills, titles)
- Entity persistence (11 types: Character, Skill, Class, Title, Event, Location, Item, Creature, Faction, Concept + relationships)
- 3-tier deduplication (exact → fuzzy → LLM-as-Judge)
- Full reconciler (all 10 entity types: Characters, Skills, Classes, Titles, Events, Locations, Items, Creatures, Factions, Concepts)
- Gemini provider (providers.py: get_gemini_client, instructor.from_gemini, LangChain ChatGoogleGenerativeAI)
- LangExtract api_key pass-through (all 4 extraction passes forward settings.gemini_api_key)
- Cost ceiling enforcement (build_book_graph / build_chapter_graph check CostTracker before each chapter)
- Embedding pipeline (local BGE-M3 or VoyageAI → Neo4j vector write-back)
- arq background workers (extraction + embedding tasks, auto-chaining)
- Book ingestion API (upload, CRUD, async extract, job polling)
- Graph explorer API (search, subgraph, neighbors, timeline, character profile)
- Admin API (cost tracking, DLQ inspection, retry endpoints)
- DLQ retry mechanism (single chapter + bulk retry-all, re-enqueue via arq)
- Ontology runtime loader (3-layer YAML loading: core → genre → series, enum validation, FastAPI dependency)
- GROUNDED_IN relationships (label-aware UNWIND per entity type, source chunk offsets)
- Reconciliation integrated in LangGraph (reconcile node after merge, alias_map in state)
- alias_map normalization (stat_changes.character, skill/class/title names, all lore entities)
- Frontend: books management, D3 force graph explorer, chat placeholder
- Docker Compose (Neo4j, Redis, PostgreSQL, LangFuse)
- 211 tests passing (golden dataset, unit, integration)

### 🔴 Not Yet Implemented
- Chat/RAG query API (hybrid retrieval: vector → rerank → LLM generate)
- Chat + Reader LangGraph agents
- Functional chat frontend (currently placeholder)
- LangGraph PostgreSQL checkpointing
- Dockerfile for app containerization
