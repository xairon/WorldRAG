# WorldRAG Documentation

![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue) ![Next.js 16](https://img.shields.io/badge/Next.js-16-black) ![Neo4j 5](https://img.shields.io/badge/Neo4j-5-green) ![Tests 211](https://img.shields.io/badge/Tests-211%20passing-brightgreen) ![License](https://img.shields.io/badge/License-Proprietary-red)

## What is WorldRAG?

WorldRAG is a state-of-the-art Knowledge Graph construction system designed for fiction novel universes. It extracts entities, relationships, events, and temporal data from novels (LitRPG, fantasy, sci-fi) and builds a rich, evolving Knowledge Graph in Neo4j.

The system combines regex pre-extraction for structured game-like elements (skills, levels, class evolutions) with four parallel LLM extraction passes for narrative content (characters, events, worldbuilding), followed by 3-tier entity deduplication and vector embedding for semantic search. All heavy processing runs asynchronously via background workers, with built-in cost tracking, circuit breakers, and dead letter queues for production reliability.

**Design principle**: Knowledge Graph construction quality is the top priority. Use cases (reader companion, chat, wiki) are built on top of the KG, not the other way around.

## Key Features

- **5-pass extraction**: 1 regex pass (free, instant) + 4 LLM passes (parallel via LangGraph)
- **3-tier entity deduplication**: exact match, fuzzy matching (thefuzz), LLM-as-Judge
- **Source grounding**: every extracted entity links back to its source text with exact character offsets
- **Chapter-based temporality**: relationships evolve over chapters (`valid_from_chapter` / `valid_to_chapter`)
- **3-layer ontology**: Core (universal) + Genre (LitRPG) + Series (Primal Hunter) -- extensible to any fiction genre
- **Async background processing**: arq workers for extraction and embedding, with automatic job chaining
- **Cost optimization**: Gemini 2.5 Flash for extraction ($0.15/M), GPT-4o-mini for reconciliation ($0.15/M), Voyage 3.5 for embeddings ($0.06/M)
- **Production resilience**: circuit breakers per LLM provider, rate limiters, tenacity retries, dead letter queue
- **Interactive graph explorer**: D3 force-directed visualization with entity search, filtering, and character profiles
- **211 tests**: golden dataset validation, unit tests, all mocked (no external dependencies)

## Architecture at a Glance

```mermaid
graph LR
    User([User]) --> Frontend[Next.js 16<br/>React 19]
    Frontend -->|REST API| Backend[FastAPI<br/>Python 3.12+]
    Backend -->|Cypher| Neo4j[(Neo4j 5)]
    Backend -->|Jobs| Redis[(Redis 7)]
    Backend -->|Extraction| LLMs[OpenAI / Gemini<br/>/ Anthropic]
    Backend -->|Embeddings| Voyage[Voyage AI]
    Redis --> Workers[arq Workers]
    Workers -->|Cypher| Neo4j
    Workers -->|API calls| LLMs
    Workers -->|Embeddings| Voyage
```

## Documentation Map

| # | Document | Description | Audience |
|---|----------|-------------|----------|
| 1 | [Architecture](./architecture.md) | System design, pipeline flow, 7 Mermaid diagrams | Developers, architects |
| 2 | [Technology Stack](./tech-stack.md) | Every technology choice with rationale ("why X, not Y") | Developers, decision-makers |
| 3 | [Data Model](./data-model.md) | Neo4j schema: 14 node labels, 11+ relationship types, all indexes | Backend developers |
| 4 | [Ontology](./ontology.md) | 3-layer ontology system with academic foundations | Researchers, domain experts |
| 5 | [Extraction Pipeline](./extraction-pipeline.md) | Deep dive: regex, 4 LLM passes, dedup, grounding, embedding | ML engineers, backend devs |
| 6 | [API Reference](./api-reference.md) | All 20 REST endpoints with schemas and examples | Frontend developers, integrators |
| 7 | [Testing](./testing.md) | Test strategy, golden dataset methodology, 211 tests | QA, contributors |
| 8 | [Deployment](./deployment.md) | Dev setup, Docker Compose, environment variables, workers | DevOps, new contributors |

**Recommended reading order**: Architecture --> Tech Stack --> Data Model --> Ontology --> Extraction Pipeline --> API Reference --> Testing --> Deployment

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/youruser/worldrag.git && cd worldrag

# 2. Configure environment
cp .env.example .env
# Edit .env: add at minimum OPENAI_API_KEY and VOYAGE_API_KEY

# 3. Start infrastructure
docker compose up -d    # Neo4j, Redis, PostgreSQL, LangFuse

# 4. Start backend + worker
uv sync
uv run uvicorn backend.app.main:app --reload --port 8000
# In a separate terminal:
uv run arq app.workers.settings.WorkerSettings

# 5. Start frontend
cd frontend && npm install && npm run dev
```

See [Deployment Guide](./deployment.md) for detailed instructions and production configuration.

## Project Status

### Complete

- Full extraction pipeline (regex + 4 parallel LLM passes via LangGraph)
- Entity persistence to Neo4j (11 entity types, 13 upsert methods)
- 3-tier deduplication (exact, fuzzy, LLM-as-Judge)
- Embedding pipeline (Voyage AI, batch 128, vector write-back)
- Background workers (arq: extraction + embedding with auto-chaining)
- REST API (20 endpoints: books, graph explorer, admin)
- Frontend (book management, D3 graph explorer, dashboard)
- Infrastructure (Docker Compose: Neo4j, Redis, PostgreSQL, LangFuse)
- 211 tests passing (golden dataset + unit tests)

### Planned

- Chat/RAG query pipeline (hybrid retrieval: vector + rerank + LLM generate)
- Chat and Reader LangGraph agents
- Complete reconciler (currently only Characters + Skills; missing 6 entity types)
- LangGraph PostgreSQL checkpointing
- Gemini provider integration in providers.py
- Application Dockerfile for containerized deployment
- Ontology runtime loader (YAML files exist but are not dynamically consumed)
