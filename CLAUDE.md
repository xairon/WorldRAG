# WorldRAG — Claude Code Instructions

## Project Overview

WorldRAG is a SOTA Knowledge Graph construction system for fiction novel universes (LitRPG, fantasy, sci-fi). It extracts entities, relationships, events, and temporal data from novels and builds a rich, evolving Neo4j Knowledge Graph.

**Priority**: KG construction quality is #1. Use cases (reader, chat, wiki) come after.

## Architecture

- **Backend**: Python 3.12+ / FastAPI (async everywhere)
- **Frontend**: Next.js 16 / React 19 / TypeScript
- **Graph DB**: Neo4j 5.x (direct Cypher, no ORM)
- **Extraction**: Instructor (structured output) — V4 single-pass GOLEM-aligned (18 entity types, 24+ relation types)
- **Ontology**: GOLEM v1.1 (General Ontology for Literary and Narrative Entities and Metadata)
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

# Evaluation
uv run python scripts/evaluate_kg.py <book_id> --chapters 10 --facts 10

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
│   ├── services/         # Business logic + extraction pipeline + embedding + evaluation
│   ├── agents/           # LangGraph graphs (extraction done; chat done; reader TODO)
│   ├── prompts/          # LLM prompt templates
│   └── workers/          # arq task queue (extraction + embedding tasks)
├── frontend/             # Next.js frontend (app/, lib/, components/, hooks/, stores/)
├── ontology/             # YAML ontology definitions (core v4.0.0 GOLEM, genre, series)
├── scripts/              # Neo4j init, migrations, seed data, evaluation
│   ├── migrations/       # PostgreSQL + Neo4j migrations
└── docker-compose.yml    # Infrastructure (Neo4j, Redis, PostgreSQL, LangFuse)
```

## Ontology Layers (GOLEM v1.1)

1. **Layer 1 (Core)**: GOLEM-aligned narrative entities — 20+ types:
   - **Characters**: Character (G1), CharacterStoff (G0, cross-work archetype), CharacterFeature (G17)
   - **Psychology**: PsychologicalState (G3, temporal emotions/beliefs/goals)
   - **Social**: SocialRelationship (G4, reified with INVOLVED_IN edges + role property)
   - **Events**: Event (G5, event_category field), NarrativeUnit (G9, programmatic)
   - **Narrative**: NarrativeSequence (G7, ex-Arc), NarrativeFunction (G10), NarrativeRole (G11)
   - **World**: Setting (G12, narrative world), Location (G13), Object (G16, ex-Item)
   - **Stoff**: NarrativeStoff (G14, cross-work archetype), TextualFeature (G18)
   - **Non-GOLEM**: Concept, Prophecy, Faction, Creature
2. **Layer 2 (Genre)**: LitRPG-specific (Class, Skill, Level, System, Title, Race, etc.)
3. **Layer 3 (Series)**: Per-series config (Bloodline, Profession, etc.)

Defined in `ontology/*.yaml`, enforced via Cypher constraints in `scripts/init_neo4j.cypher`.
Loaded at runtime by `OntologyLoader` (app/core/ontology_loader.py) with enum validation, golem_alignment tracking, disjointness rules, and co-evolutionary induction support.

## Important Patterns

- **V4 extraction (SOTA)**: Single-pass Instructor pipeline — entities → verify_coverage → relations → verify_extractions → mention_detect → reconcile_persist
- **V3 extraction (legacy)**: 4-pass LangExtract parallel fan-out (characters|systems|events|lore) — still available via `use_v3_pipeline=True`
- **Provider routing**: `provider:model` spec everywhere (e.g. `openrouter:deepseek/deepseek-chat-v3-0324`, `local:qwen3:32b`, `gemini:gemini-2.5-flash`)
- **Entity resolution**: Article-tolerant lookup → Exact match → Fuzzy (thefuzz) → S-BERT clustering → LLM-as-Judge
- **Temporality**: Chapter-based (valid_from_chapter/valid_to_chapter), not datetime
- **Source grounding**: Every entity links back to its source chunk with char offsets
- **Cost optimization**: Gemini 2.5 Flash (free tier) or DeepSeek V3.2 via OpenRouter ($0.26/M input)
- **Async workers**: POST /books/{id}/extract/v4 enqueues arq job, auto-chains embedding on completion
- **Fulltext search**: entity_fulltext Neo4j index (19 labels) with Lucene escaping + CONTAINS fallback
- **Graph visualization**: Sigma.js + graphology (ForceAtlas2 layout) — not D3
- **MINE benchmark**: KGGen-inspired (NeurIPS 2025) KG quality evaluation via `scripts/evaluate_kg.py`

## Pipeline Flow

```
Upload (epub/pdf/txt)
  → Parse chapters (ingestion.py)
  → Chunk chapters (chunking.py)
  → Regex extract — Passe 0 (regex_extractor.py)
  → Store in Neo4j (book_repo.py)
  → [Status: completed]

Extract V4 (arq worker — async, POST /books/{id}/extract/v4)
  → Joint pattern + ontology induction (first 3 chapters, GOLEM-aware)
  → LangGraph 6-node linear pipeline per chapter:
      1. extract_entities (Instructor — 18 entity types, GOLEM v1.1 aligned)
      2. verify_coverage (2nd LLM pass for missed entities)
      3. extract_relations (Instructor — 24+ relation types)
      4. verify_extractions (text grounding + GOLEM validation rules)
      5. mention_detect (programmatic name/alias matching)
      6. reconcile_persist (3-tier dedup + character ref resolution + NarrativeUnit generation + alias_map + Neo4j upsert)
  → EntityRegistry context accumulates across chapters (article-tolerant lookup)
  → Book-level post-processing (12 steps):
      1. Iterative clustering (KGGen-style S-BERT + BM25)
      2. Entity summaries (LLM)
      3. State snapshots
      4. Community detection (Leiden)
      5. Orphan GOLEM entity resolution
      6. Relation reclassification (RELATES_TO → SocialRelationship)
      7. Topology inference (LightKGG-inspired: FOLLOWS_STATE, TRIGGERS_EVENT, SEQUENCED_IN, ROLE_IN_SEQUENCE)
      8. Description enrichment (LLM batch, concurrent)
      9. GenreEntity conceptualization (AutoSchemaKG-inspired)
      10. Programmatic GOLEM edges (CHARACTER_IN_WORK, SETTING_OF_WORK)
      11. CharacterStoff creation (multi-series, Phase E)
      12. Auto-enqueue embedding job
  → DLQ for failed chapters
  → [Status: extracted]

Embed (arq worker — async)
  → Fetch chunks without embeddings
  → VoyageAI batch embed (128/batch)
  → UNWIND write-back to Neo4j
  → Cost tracking
  → [Status: embedded]
```

## What's Done vs TODO

**Done**: GOLEM v1.1 ontology refactor (core.yaml v4.0.0, 6 phases A-F), V4 extraction pipeline (Instructor, 6-node LangGraph, 18 entity types, 24+ relation types), V3 legacy pipeline (backward-compatible), 3-tier dedup + KGGen-style clustering, reconciler with GOLEM character reference resolution, book-level post-processing (12 steps including topology inference + description enrichment + relation reclassification + conceptualization), MINE benchmark, embedding pipeline, arq workers, book ingestion API, graph explorer API, admin API (costs + DLQ), ontology loader (GOLEM-aware with disjointness + co-evolutionary induction), frontend (books + Sigma.js graph explorer + chat UI + ontology viewer with GOLEM category grouping), Docker Compose, OpenRouter/Gemini/Ollama multi-provider support, 1100+ tests.

**Also done**:
- ~~Chat/RAG query API~~ ✅ Done (hybrid retrieval: vector → rerank → LLM)
- ~~Chat LangGraph agent (17 nodes, 8 routes, NLI faithfulness)~~ ✅ Done (includes psychological_qa route)
- ~~Chat frontend (thread sidebar, citations, confidence badge, feedback)~~ ✅ Done
- ~~LangGraph PostgreSQL checkpointing~~ ✅ Done
- ~~Chat feedback API (PostgreSQL)~~ ✅ Done
- ~~GOLEM v1.1 refactor (6 phases)~~ ✅ Done
- ~~KG quality improvements (3 phases)~~ ✅ Done

**Remaining**: Reader LangGraph agent (summarization, highlights), Frontend polish, Production deployment config.

## Academic References

- **GOLEM v1.1**: Pianzola et al. (2024) — General Ontology for Literary and Narrative Entities and Metadata
- **KGGen**: Stanford/Toronto (NeurIPS 2025) — Entity resolution S-BERT+BM25, MINE benchmark
- **AutoSchemaKG**: HKUST (2025) — Autonomous schema induction, conceptualization
- **LightKGG**: (2025) — Topology-enhanced relationship inference
- **OneKE**: ZJU (WWW 2025) — Multi-agent schema-guided extraction
- **DOLCE**: Upper ontology (endurant/perdurant, agentive/non-agentive)
- **CIDOC-CRM**: ISO 21127 — Event-temporal model
- **LRMoo**: IFLA/CIDOC — Bibliographic hierarchy Work/Expression
