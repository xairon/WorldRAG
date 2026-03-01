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
- **Embeddings**: VoyageAI (voyage-3.5) via batch pipeline
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

Detailed conventions are in `.claude/rules/` (path-scoped, auto-loaded). Key points:

- **Python**: async everywhere, Pydantic v2, structlog (never print), absolute imports, tenacity retries
- **TypeScript**: strict mode, App Router, Server Components by default, shadcn/ui + Tailwind
- **Neo4j**: MERGE not CREATE, parameterized queries ($param), batch_id on all writes, temporal valid_from/to_chapter
- **Logging**: Never `error=str(e)` — use `exc_info=True` or `type(e).__name__`

## Project Structure

```
WorldRAG/
├── backend/app/          # FastAPI backend
│   ├── api/              # Routes + middleware + auth + dependencies
│   ├── core/             # Logging, resilience, rate limiting, cost tracking, DLQ
│   ├── llm/              # LLM providers, embeddings (Voyage), reranker (Cohere)
│   ├── schemas/          # Pydantic models
│   ├── repositories/     # Neo4j data access (base, book_repo, entity_repo)
│   ├── services/         # Business logic + extraction pipeline + embedding
│   ├── agents/           # LangGraph graphs (extraction done; reader, chat TODO)
│   ├── prompts/          # LLM prompt templates
│   └── workers/          # arq task queue (extraction + embedding tasks)
├── frontend/             # Next.js frontend (app/, lib/, components/, hooks/, stores/)
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
- **Cost optimization**: Gemini 2.5 Flash for extraction, GPT-4o-mini for reconciliation
- **Async workers**: POST /books/{id}/extract enqueues arq job, auto-chains embedding on completion
- **Fulltext search**: entity_fulltext Neo4j index with Lucene escaping + CONTAINS fallback
- **Graph visualization**: Sigma.js + graphology (ForceAtlas2 layout) — not D3

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
  → VoyageAI batch embed (128/batch)
  → UNWIND write-back to Neo4j
  → Cost tracking
  → [Status: embedded]
```

## What's Done vs TODO

**Done**: Full extraction pipeline (LangGraph 4-pass + regex), 11 entity types, 3-tier dedup, reconciler, embedding pipeline (VoyageAI), arq workers, book ingestion API, graph explorer API, admin API (costs + DLQ), ontology loader, frontend (books + Sigma.js graph explorer), Docker Compose, ~586 tests.

**TODO**: Chat/RAG query API (hybrid retrieval: vector → rerank → LLM), Chat + Reader LangGraph agents, functional chat frontend, LangGraph PostgreSQL checkpointing.
