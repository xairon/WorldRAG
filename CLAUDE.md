# WorldRAG — Claude Code Instructions

## Project Overview

WorldRAG is a SOTA Knowledge Graph construction system for fiction novel universes (LitRPG, fantasy, sci-fi). It extracts entities, relationships, events, and temporal data from novels and builds a rich, evolving Neo4j Knowledge Graph.

**Priority**: KG construction quality is #1. Use cases (reader, chat, wiki) come after.

## Architecture

- **Backend**: Python 3.12+ / FastAPI (async everywhere)
- **Frontend**: Next.js 15 / React 19 / TypeScript
- **Graph DB**: Neo4j 5.x (direct Cypher, no ORM)
- **Extraction**: LangExtract (grounded) + Instructor (reconciliation)
- **Orchestration**: LangGraph (3 separate graphs: extraction, reader, chat)
- **Monitoring**: LangFuse (self-hosted) + structlog
- **Task Queue**: arq + Redis
- **Checkpointing**: PostgreSQL (LangGraph AsyncPostgresSaver)

## Key Commands

```bash
# Backend
uv run uvicorn backend.app.main:app --reload --port 8000
uv run pytest backend/tests/ -x -v
uv run ruff check backend/ --fix
uv run ruff format backend/
uv run pyright backend/

# Frontend
cd frontend && npm run dev
cd frontend && npm run build

# Infrastructure
docker compose up -d          # Neo4j + Redis + PostgreSQL + LangFuse
docker compose down

# Neo4j
# Browser: http://localhost:7474 (neo4j/worldrag)
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

### TypeScript (frontend/)
- TypeScript strict mode
- Next.js 15 App Router (not Pages)
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
│   ├── api/              # Routes + middleware + dependencies
│   ├── core/             # Logging, resilience, rate limiting, cost tracking
│   ├── llm/              # LLM providers, embeddings, reranker
│   ├── schemas/          # Pydantic models
│   ├── repositories/     # Neo4j data access
│   ├── services/         # Business logic + extraction pipeline
│   ├── agents/           # LangGraph graphs (extraction, reader, chat)
│   ├── prompts/          # LLM prompt templates
│   └── workers/          # arq task queue workers
├── frontend/src/         # Next.js frontend
├── ontology/             # YAML ontology definitions (core, genre, series)
├── scripts/              # Neo4j init, migrations, seed data
└── docker-compose.yml    # Infrastructure
```

## Ontology Layers

1. **Layer 1 (Core)**: Universal narrative entities (Character, Event, Location, Item, Arc)
2. **Layer 2 (Genre)**: LitRPG-specific (Class, Skill, Level, System, Title)
3. **Layer 3 (Series)**: Per-series config (Bloodline, Profession, etc.)

Defined in `ontology/*.yaml`, enforced via Cypher constraints in `scripts/init_neo4j.cypher`.

## Important Patterns

- **Two-pass extraction**: Regex (Passe 0) for blue boxes/stats → LLM (Passes 1-4) for narrative
- **Entity resolution**: Exact match → Fuzzy (thefuzz) → Embedding similarity + LLM-as-Judge
- **Temporality**: Chapter-based (valid_from_chapter/valid_to_chapter), not datetime
- **Source grounding**: Every entity links back to its source chunk with char offsets
- **Cost optimization**: Gemini 2.5 Flash for extraction, GPT-4o-mini for reconciliation
