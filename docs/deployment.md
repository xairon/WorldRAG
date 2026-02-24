# Deployment & Setup Guide

> Complete guide for setting up WorldRAG in development: prerequisites, infrastructure, environment configuration, database initialization, and worker management.

**Back to**: [Documentation Hub](./README.md)

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Infrastructure Services](#infrastructure-services)
- [Environment Variables](#environment-variables)
- [Database Initialization](#database-initialization)
- [Running the Application](#running-the-application)
- [Worker Management](#worker-management)
- [Service Architecture](#service-architecture)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.12+ | Backend runtime |
| uv | latest | Package manager & runner |
| Node.js | 20+ | Frontend runtime |
| Docker & Docker Compose | latest | Infrastructure services |
| Git | latest | Version control |

### API Keys Required

| Provider | Key | Used For |
|----------|-----|----------|
| Google AI | `GOOGLE_API_KEY` | Gemini 2.5 Flash (extraction) |
| OpenAI | `OPENAI_API_KEY` | GPT-4o-mini (reconciliation) |
| Voyage AI | `VOYAGE_API_KEY` | voyage-3.5 (embeddings) |

---

## Quick Start

```bash
# 1. Clone and install
git clone <repo-url> && cd WorldRAG
uv sync                          # Python dependencies
cd frontend && npm install && cd ..  # JS dependencies

# 2. Start infrastructure
docker compose up -d

# 3. Configure environment
cp .env.example .env             # Edit with your API keys

# 4. Initialize Neo4j schema
# Open http://localhost:7474 (neo4j/worldrag)
# Paste and run scripts/init_neo4j.cypher

# 5. Start backend
python -m uv run uvicorn backend.app.main:app --reload --port 8000

# 6. Start frontend (separate terminal)
cd frontend && npm run dev

# 7. Start background worker (separate terminal)
python -m uv run arq app.workers.settings.WorkerSettings

# 8. Verify
curl http://localhost:8000/health
# → {"status": "healthy", "services": {"neo4j": "ok", "redis": "ok", ...}}
```

---

## Infrastructure Services

```mermaid
graph LR
    subgraph Docker["Docker Compose"]
        Neo4j["Neo4j 5<br/>:7474 / :7687"]
        Redis["Redis 7<br/>:6379"]
        PG["PostgreSQL 16<br/>:5432"]
        LF["LangFuse 2<br/>:3001"]
        LFDB["LangFuse DB<br/>(internal)"]
    end

    Backend["FastAPI<br/>:8000"] --> Neo4j
    Backend --> Redis
    Backend --> PG
    Backend --> LF
    Worker["arq Worker"] --> Neo4j
    Worker --> Redis
    Frontend["Next.js<br/>:3000"] --> Backend
    LF --> LFDB

    style Docker fill:#1e3a5f,stroke:#4a90d9,color:#fff
    style Backend fill:#2d4a2d,stroke:#4ad94a,color:#fff
    style Worker fill:#5f3a1e,stroke:#d99a4a,color:#fff
    style Frontend fill:#3a1e5f,stroke:#9a4ad9,color:#fff
```

### Docker Compose Services

#### Neo4j 5 Community

```yaml
neo4j:
  image: neo4j:5-community
  ports:
    - "127.0.0.1:7474:7474"   # Browser UI
    - "127.0.0.1:7687:7687"   # Bolt protocol
  environment:
    NEO4J_AUTH: neo4j/${NEO4J_PASSWORD:-worldrag}
    NEO4J_PLUGINS: '["apoc"]'
    NEO4J_dbms_memory_heap_max__size: "2G"
    NEO4J_dbms_memory_pagecache_size: "1G"
  volumes:
    - neo4j_data:/data
  mem_limit: 4g
```

- **Browser**: http://localhost:7474
- **Credentials**: `neo4j` / `worldrag` (default)
- **APOC plugin**: Enabled for `apoc.path.subgraphAll` (graph exploration)
- **Memory**: 2G heap + 1G page cache (adjust for larger datasets)

#### Redis 7

```yaml
redis:
  image: redis:7-alpine
  ports:
    - "127.0.0.1:6379:6379"
  command: redis-server --requirepass ${REDIS_PASSWORD:-worldrag}
  mem_limit: 512m
```

- **Password**: `worldrag` (default)
- **Usage**: arq task queue, DLQ storage, rate limiter state
- **Memory**: 512MB (sufficient for queue metadata)

#### PostgreSQL 16

```yaml
postgres:
  image: postgres:16-alpine
  ports:
    - "127.0.0.1:5432:5432"
  environment:
    POSTGRES_USER: ${POSTGRES_USER:-worldrag}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-worldrag}
    POSTGRES_DB: ${POSTGRES_DB:-worldrag}
  mem_limit: 1g
```

- **Credentials**: `worldrag` / `worldrag`
- **Database**: `worldrag`
- **Usage**: LangGraph checkpointing (planned — AsyncPostgresSaver)

#### LangFuse 2

```yaml
langfuse:
  image: langfuse/langfuse:2
  ports:
    - "127.0.0.1:3001:3000"
  depends_on:
    langfuse-db: { condition: service_healthy }
```

- **UI**: http://localhost:3001
- **Usage**: LLM observability, trace inspection, cost monitoring
- **Has its own PostgreSQL** (`langfuse-db`) — separate from the app database

### Docker Commands

```bash
# Start all services
docker compose up -d

# Check service health
docker compose ps

# View Neo4j logs
docker compose logs neo4j -f

# Stop all services
docker compose down

# Reset all data (nuclear option)
docker compose down -v  # removes volumes!
```

---

## Environment Variables

Create a `.env` file in the project root:

```bash
# ── LLM Providers ────────────────────────────────────────────
GOOGLE_API_KEY=your-google-ai-key          # Gemini 2.5 Flash
OPENAI_API_KEY=your-openai-key             # GPT-4o-mini
VOYAGE_API_KEY=your-voyage-key             # voyage-3.5

# ── Infrastructure ───────────────────────────────────────────
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=worldrag

REDIS_URL=redis://:worldrag@localhost:6379/0

POSTGRES_URL=postgresql://worldrag:worldrag@localhost:5432/worldrag

# ── Auth ─────────────────────────────────────────────────────
WORLDRAG_API_KEY=your-api-key              # Bearer token for API
WORLDRAG_ADMIN_KEY=your-admin-key          # Admin endpoints

# ── LangFuse (optional) ─────────────────────────────────────
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3001

# ── Cost Ceilings ────────────────────────────────────────────
COST_CEILING_PER_CHAPTER=0.50              # Max $ per chapter
COST_CEILING_PER_BOOK=50.00               # Max $ per book
```

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | structlog level |
| `LOG_FORMAT` | `json` | `json` or `console` |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins |
| `MAX_FILE_SIZE` | `104857600` | Upload size limit (100 MB) |

---

## Database Initialization

### Neo4j Schema

On first setup (or after a full reset), initialize the Neo4j schema:

**Option 1: Neo4j Browser** (recommended)

1. Open http://localhost:7474
2. Login with `neo4j` / `worldrag`
3. Copy-paste the contents of `scripts/init_neo4j.cypher`
4. Execute

**Option 2: cypher-shell**

```bash
cat scripts/init_neo4j.cypher | docker exec -i worldrag-neo4j-1 \
  cypher-shell -u neo4j -p worldrag
```

### What It Creates

- **15 uniqueness constraints** (one per entity type)
- **12 property indexes** (fast lookups)
- **10 batch rollback indexes** (batch_id per entity type)
- **9 fulltext indexes** (Lucene text search)
- **1 vector index** (cosine similarity, 1024 dimensions)
- **8 relationship property indexes** (temporal queries)

### Verification

```cypher
SHOW CONSTRAINTS;  -- Should show 15 constraints
SHOW INDEXES;      -- Should show 40+ indexes
```

---

## Running the Application

### Backend (FastAPI)

```bash
# Development (auto-reload)
python -m uv run uvicorn backend.app.main:app --reload --port 8000

# Production-like
python -m uv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**API docs**: http://localhost:8000/docs (Swagger UI)

### Frontend (Next.js)

```bash
cd frontend

# Development
npm run dev          # → http://localhost:3000

# Production build
npm run build
npm start
```

### Background Worker (arq)

```bash
# Required: Redis + Neo4j must be running
python -m uv run arq app.workers.settings.WorkerSettings
```

The worker processes:
- `process_book_extraction` — LLM extraction pipeline
- `process_book_embedding` — Voyage AI batch embedding

Jobs are auto-chained: extraction completion enqueues embedding automatically.

---

## Worker Management

### Monitoring Workers

```bash
# Check Redis queue
redis-cli -a worldrag LLEN worldrag:arq:queue
redis-cli -a worldrag KEYS "arq:*"

# Check job status via API
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8000/api/v1/books/{book_id}/jobs
```

### Scaling

For faster extraction of large books:

```bash
# Run multiple worker instances (each picks up different jobs)
python -m uv run arq app.workers.settings.WorkerSettings &
python -m uv run arq app.workers.settings.WorkerSettings &
```

Workers are idempotent — multiple instances safely process different chapters.

### DLQ Management

```bash
# Check failed chapters
curl -H "Authorization: Bearer $ADMIN_KEY" \
  http://localhost:8000/api/v1/admin/dlq

# Retry a single failed chapter
curl -X POST -H "Authorization: Bearer $ADMIN_KEY" \
  http://localhost:8000/api/v1/admin/dlq/retry/{book_id}/{chapter}

# Retry all failed chapters (one job per book)
curl -X POST -H "Authorization: Bearer $ADMIN_KEY" \
  http://localhost:8000/api/v1/admin/dlq/retry-all

# Clear all failures without retrying
curl -X POST -H "Authorization: Bearer $ADMIN_KEY" \
  http://localhost:8000/api/v1/admin/dlq/clear
```

---

## Service Architecture

### Port Map

| Service | Port | Protocol | URL |
|---------|------|----------|-----|
| FastAPI | 8000 | HTTP | http://localhost:8000 |
| Next.js | 3000 | HTTP | http://localhost:3000 |
| Neo4j Browser | 7474 | HTTP | http://localhost:7474 |
| Neo4j Bolt | 7687 | Bolt | bolt://localhost:7687 |
| Redis | 6379 | RESP | redis://localhost:6379 |
| PostgreSQL | 5432 | TCP | postgresql://localhost:5432 |
| LangFuse | 3001 | HTTP | http://localhost:3001 |

### Health Checks

All Docker services have health checks configured:

```bash
# Quick check — all services
curl http://localhost:8000/health
```

Expected response when all services are healthy:
```json
{
  "status": "healthy",
  "services": {
    "neo4j": "ok",
    "redis": "ok",
    "postgres": "ok",
    "langfuse": "ok"
  }
}
```

### Readiness vs. Liveness

| Probe | Endpoint | Checks | Use For |
|-------|----------|--------|---------|
| Liveness | `GET /health/live` | Process alive | Container restart |
| Readiness | `GET /health/ready` | Neo4j connected | Load balancer routing |
| Full | `GET /health` | All services | Monitoring dashboard |

---

## Troubleshooting

### Neo4j won't start

```bash
# Check logs
docker compose logs neo4j

# Common: port already in use
lsof -i :7474    # or netstat -ano | findstr 7474 on Windows

# Reset Neo4j data
docker compose down
docker volume rm worldrag_neo4j_data
docker compose up -d neo4j
```

### Redis connection refused

```bash
# Verify Redis is running
docker compose ps redis

# Test connection
redis-cli -a worldrag ping
# Expected: PONG
```

### Worker not picking up jobs

```bash
# 1. Check Redis connection
redis-cli -a worldrag ping

# 2. Check queue has jobs
redis-cli -a worldrag LLEN worldrag:arq:queue

# 3. Check worker logs (run in foreground)
python -m uv run arq app.workers.settings.WorkerSettings

# 4. Common issue: wrong queue name
# Worker must listen on "worldrag:arq" queue
```

### Import errors

```bash
# Ensure you're in the project root
pwd  # should be .../WorldRAG

# Ensure dependencies are installed
uv sync

# Run with uv (resolves PYTHONPATH)
python -m uv run uvicorn backend.app.main:app --reload --port 8000
```

### "Book status is 'pending'" error on extraction

The book must be ingested first:
1. Upload via `POST /books` → status becomes `completed`
2. Then extract via `POST /books/{id}/extract`

### Neo4j constraint violations

If you see "already exists with label Character and property canonical_name":
- This is expected behavior — MERGE handles it
- If it's causing failures, check that extraction is using MERGE, not CREATE
- Run `SHOW CONSTRAINTS` to verify schema is correct

---

**Back to**: [Documentation Hub](./README.md)
