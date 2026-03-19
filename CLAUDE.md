# WorldRAG — Claude Code Instructions

## Project Overview

WorldRAG is a SOTA Knowledge Graph construction system for fiction novel universes (LitRPG, fantasy, sci-fi). It extracts entities, relationships, events, and temporal data from novels and builds a rich, evolving Neo4j Knowledge Graph.

**Priority**: KG construction quality is #1. Use cases (reader, chat, wiki) come after.

## Architecture

- **Backend**: Python 3.12+ / FastAPI (async everywhere)
- **Frontend**: Next.js 16 / React 19 / TypeScript
- **Graph DB**: Neo4j 5.x (direct Cypher, no ORM)
- **Extraction**: Instructor (structured output) — V4 single-pass KGGen-style (15 entity types, 16 relation types)
- **LLM Providers**: Gemini (default), OpenRouter (DeepSeek V3.2 etc.), Ollama (local) — all via `provider:model` spec
- **Orchestration**: LangGraph (3 separate graphs: extraction, reader, chat)
- **Monitoring**: LangFuse (self-hosted) + structlog
- **Task Queue**: arq + Redis
- **Embeddings**: BGE-m3 (local, sentence-transformers) via batch pipeline, VoyageAI (voyage-3.5) as alt
- **Reranker**: zerank-1-small (local CrossEncoder, sentence-transformers) — wired to chat pipeline
- **Checkpointing**: PostgreSQL (LangGraph AsyncPostgresSaver) — active in chat pipeline

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

# Neo4j Browser: http://localhost:49520 (neo4j/worldrag)
# LangFuse: http://localhost:49517
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
│   ├── llm/              # LLM providers, embeddings (local BGE-m3), reranker (zerank-1-small)
│   ├── schemas/          # Pydantic models
│   ├── repositories/     # Neo4j data access (base, book_repo, entity_repo)
│   ├── services/         # Business logic + extraction pipeline + embedding
│   ├── agents/           # LangGraph graphs (extraction done; chat done; reader TODO)
│   ├── prompts/          # LLM prompt templates
│   └── workers/          # arq task queue (extraction + embedding tasks)
├── frontend/             # Next.js frontend (app/, lib/, components/, hooks/, stores/)
├── ontology/             # YAML ontology definitions (core, genre, series)
├── scripts/              # Neo4j init, migrations, seed data
│   ├── migrations/       # PostgreSQL Alembic migrations
└── docker-compose.yml    # Infrastructure (Neo4j, Redis, PostgreSQL, LangFuse)
```

## Ontology Layers

1. **Layer 1 (Core)**: Universal narrative entities (Character, Event, Location, Item, Arc)
2. **Layer 2 (Genre)**: LitRPG-specific (Class, Skill, Level, System, Title)
3. **Layer 3 (Series)**: Per-series config (Bloodline, Profession, etc.)

Defined in `ontology/*.yaml`, enforced via Cypher constraints in `scripts/init_neo4j.cypher`.
Loaded at runtime by `OntologyLoader` (app/core/ontology_loader.py) with enum validation.

## Important Patterns

- **V4 extraction (SOTA)**: Single-pass Instructor pipeline — entities → relations → mention_detect → reconcile_persist
- **V3 extraction (legacy)**: 4-pass LangExtract parallel fan-out (characters|systems|events|lore) — still available via `use_v3_pipeline=True`
- **Provider routing**: `provider:model` spec everywhere (e.g. `openrouter:deepseek/deepseek-chat-v3-0324`, `local:qwen3:32b`, `gemini:gemini-2.5-flash`)
- **Entity resolution**: Exact match → Fuzzy (thefuzz) → Embedding similarity + LLM-as-Judge
- **Temporality**: Chapter-based (valid_from_chapter/valid_to_chapter), not datetime
- **Source grounding**: Every entity links back to its source chunk with char offsets
- **Cost optimization**: Gemini 2.5 Flash (free tier) or DeepSeek V3.2 via OpenRouter ($0.26/M input)
- **Async workers**: POST /books/{id}/extract/v4 enqueues arq job, auto-chains embedding on completion
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

Extract V4 (arq worker — async, POST /books/{id}/extract/v4)
  → LangGraph 4-node linear pipeline per chapter:
      1. extract_entities (Instructor — 15 entity types in one call)
      2. extract_relations (Instructor — 16 relation types)
      3. mention_detect (programmatic name/alias matching)
      4. reconcile_persist (3-tier dedup + alias_map + Neo4j upsert)
  → EntityRegistry context accumulates across chapters
  → Book-level post-processing: clustering → summaries → communities
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

**Done**: V4 extraction pipeline (Instructor, 4-node LangGraph, 15 entity types, 16 relation types), V3 legacy pipeline (LangExtract, 4-pass), 3-tier dedup, reconciler, book-level post-processing (clustering + summaries + communities), embedding pipeline (VoyageAI), arq workers, book ingestion API, graph explorer API, admin API (costs + DLQ), ontology loader, frontend (books + Sigma.js graph explorer + chat UI), Docker Compose, OpenRouter/Gemini/Ollama multi-provider support, 1000+ tests.

**Also done**:
- ~~Chat/RAG query API~~ ✅ Done (hybrid retrieval: vector → rerank → LLM)
- ~~Chat LangGraph agent (17 nodes, 6 routes, NLI faithfulness)~~ ✅ Done
- ~~Chat frontend (thread sidebar, citations, confidence badge, feedback)~~ ✅ Done
- ~~LangGraph PostgreSQL checkpointing~~ ✅ Done
- ~~Chat feedback API (PostgreSQL)~~ ✅ Done

**Remaining**: Reader LangGraph agent (summarization, highlights), Frontend polish, Production deployment config.
