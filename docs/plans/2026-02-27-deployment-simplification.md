# Deployment Simplification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** One `docker compose up` launches the full WorldRAG stack (6 services) with zero manual steps.

**Architecture:** Remove LangFuse (2 containers), add frontend to Docker with volume mounts for hot-reload, proxy API calls through Next.js rewrites (eliminates CORS/CSP/port issues), auto-init Neo4j schema on backend startup.

**Tech Stack:** Docker Compose, Next.js rewrites, multi-stage Dockerfiles, FastAPI lifespan hooks.

---

### Task 1: Create frontend Dockerfile

**Files:**
- Create: `frontend/Dockerfile`

**Step 1: Create the multi-stage Dockerfile**

```dockerfile
FROM node:22-alpine AS base
WORKDIR /app
COPY package.json package-lock.json ./

# ── Dev target (hot-reload via volume mount) ─────────────────────────
FROM base AS dev
RUN npm ci
# Source mounted as volume in docker-compose — don't COPY
CMD ["npx", "next", "dev", "--hostname", "0.0.0.0"]

# ── Builder (production) ─────────────────────────────────────────────
FROM base AS builder
RUN npm ci
COPY . .
RUN npm run build

# ── Prod target ──────────────────────────────────────────────────────
FROM node:22-alpine AS prod
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
ENV HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
```

**Step 2: Add `.dockerignore` for frontend**

Create `frontend/.dockerignore`:
```
node_modules
.next
.env*
```

**Step 3: Commit**

```bash
git add frontend/Dockerfile frontend/.dockerignore
git commit -m "feat(deploy): add frontend Dockerfile with dev/prod targets"
```

---

### Task 2: Add Next.js API proxy rewrites

**Files:**
- Modify: `frontend/next.config.ts` (lines 1–24)
- Modify: `frontend/lib/api/client.ts` (line 5)
- Modify: `frontend/hooks/use-extraction-progress.ts` (line 4, 44)
- Modify: `frontend/lib/api/chat.ts` (line 1, 66)

**Step 1: Add rewrites to next.config.ts**

In `frontend/next.config.ts`, add the `rewrites` function and fix CSP.

Replace the entire file with:

```typescript
import type { NextConfig } from "next"

const BACKEND_URL = process.env.BACKEND_URL ?? "http://backend:8000"

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` },
    ]
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Content-Security-Policy",
            value:
              "default-src 'self'; script-src 'self' 'unsafe-eval' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self';",
          },
        ],
      },
    ]
  },
}

export default nextConfig
```

Key changes:
- `BACKEND_URL` env var for Docker internal networking (default `http://backend:8000`)
- `output: "standalone"` for production Docker builds
- `rewrites()` proxies `/api/*` to backend
- CSP `connect-src` changed from `http://localhost:8000` to `'self'`

**Step 2: Change API_BASE to relative path**

In `frontend/lib/api/client.ts` line 5, change:

```typescript
// OLD
export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api"

// NEW
export const API_BASE = "/api"
```

This works because Next.js rewrites proxy `/api/*` to the backend.

**Step 3: Remove direct API_BASE import from SSE hooks**

In `frontend/hooks/use-extraction-progress.ts`, the SSE URL on line 44 already uses `API_BASE`:
```typescript
const url = `${API_BASE}/stream/extraction/${bookId}`
```
This now resolves to `/api/stream/extraction/${bookId}` — proxied by Next.js. No change needed.

In `frontend/lib/api/chat.ts` line 66:
```typescript
const url = `${API_BASE}/chat/stream?${params.toString()}`
```
Same — already works via relative path. No change needed.

**Step 4: Delete frontend/.env.local**

```bash
rm frontend/.env.local
```

**Step 5: Run type-check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: PASS (no type errors)

**Step 6: Commit**

```bash
git add frontend/next.config.ts frontend/lib/api/client.ts
git rm -f frontend/.env.local
git commit -m "feat(deploy): proxy API through Next.js rewrites, remove hardcoded URLs"
```

---

### Task 3: Auto-init Neo4j schema on backend startup

**Files:**
- Modify: `backend/app/main.py` (after line 64, inside lifespan neo4j section)

**Step 1: Add schema init after Neo4j connectivity check**

After line 64 (`logger.info("neo4j_connected", ...)`), add:

```python
# Auto-init schema if empty (first boot)
async with neo4j_driver.session() as session:
    result = await session.run("SHOW CONSTRAINTS")
    constraints = await result.data()
    if len(constraints) == 0:
        logger.info("neo4j_schema_empty_initializing")
        cypher_path = Path(__file__).resolve().parents[2] / "scripts" / "init_neo4j.cypher"
        if cypher_path.exists():
            cypher_text = cypher_path.read_text(encoding="utf-8")
            statements = [
                s.strip() for s in cypher_text.split(";")
                if s.strip() and not s.strip().startswith("//")
            ]
            for stmt in statements:
                await session.run(stmt)
            logger.info("neo4j_schema_initialized", statements=len(statements))
        else:
            logger.warning("neo4j_schema_file_not_found", path=str(cypher_path))
    else:
        logger.info("neo4j_schema_already_initialized", constraints=len(constraints))
```

Also add `from pathlib import Path` at the top of `main.py` if not already imported.

**Step 2: Verify the path resolves correctly**

`Path(__file__).resolve().parents[2]` from `backend/app/main.py` = project root. Verify:
```bash
cd E:/RAG && python -c "from pathlib import Path; print(Path('backend/app/main.py').resolve().parents[2])"
```
Expected: `E:\RAG`

**Step 3: Lint**

```bash
uv run ruff check backend/app/main.py --fix
```

**Step 4: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(deploy): auto-init Neo4j schema on first startup"
```

---

### Task 4: Improve backend Dockerfile

**Files:**
- Modify: `Dockerfile` (lines 21–37, runtime stage)

**Step 1: Add non-root user and healthcheck**

Replace the runtime stage (lines 21–37) with:

```dockerfile
# ── Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r worldrag && useradd -r -g worldrag -d /app worldrag

WORKDIR /app

COPY --from=builder --chown=worldrag:worldrag /app/.venv .venv
COPY --chown=worldrag:worldrag backend/ backend/
COPY --chown=worldrag:worldrag ontology/ ontology/
COPY --chown=worldrag:worldrag scripts/ scripts/
COPY --chown=worldrag:worldrag pyproject.toml .

ENV PATH="/app/.venv/bin:$PATH"

USER worldrag
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=5 --start-period=15s \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Key changes: non-root user `worldrag`, `curl` installed for healthcheck, `HEALTHCHECK` instruction.

**Step 2: Commit**

```bash
git add Dockerfile
git commit -m "feat(deploy): non-root user, curl healthcheck in backend Dockerfile"
```

---

### Task 5: Rewrite docker-compose.yml

**Files:**
- Rewrite: `docker-compose.yml`

**Step 1: Replace docker-compose.yml entirely**

```yaml
services:
  neo4j:
    image: neo4j:5-community
    restart: unless-stopped
    ports:
      - "${BIND_HOST:-127.0.0.1}:7474:7474"
      - "${BIND_HOST:-127.0.0.1}:7687:7687"
    environment:
      NEO4J_AUTH: neo4j/${NEO4J_PASSWORD:-worldrag}
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_dbms_memory_heap_max__size: "2G"
      NEO4J_dbms_memory_pagecache_size: "1G"
      NEO4J_dbms_security_procedures_allowlist: "apoc.path.*,apoc.cypher.*,apoc.meta.*"
    volumes:
      - neo4j_data:/data
    mem_limit: 4g
    healthcheck:
      test: ["CMD", "neo4j", "status"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "${BIND_HOST:-127.0.0.1}:6379:6379"
    command: redis-server --requirepass ${REDIS_PASSWORD:-worldrag}
    volumes:
      - redis_data:/data
    mem_limit: 512m
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD:-worldrag}", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    ports:
      - "${BIND_HOST:-127.0.0.1}:5432:5432"
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-worldrag}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-worldrag}
      POSTGRES_DB: ${POSTGRES_DB:-worldrag}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    mem_limit: 1g
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-worldrag}"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend:
    build: .
    restart: unless-stopped
    ports:
      - "${BIND_HOST:-127.0.0.1}:8000:8000"
    env_file: .env
    environment:
      NEO4J_URI: bolt://neo4j:7687
      REDIS_URL: redis://:${REDIS_PASSWORD:-worldrag}@redis:6379
      POSTGRES_URI: postgresql://${POSTGRES_USER:-worldrag}:${POSTGRES_PASSWORD:-worldrag}@postgres:5432/${POSTGRES_DB:-worldrag}
    depends_on:
      neo4j:
        condition: service_healthy
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    mem_limit: 2g

  worker:
    build: .
    restart: unless-stopped
    command: ["python", "-m", "arq", "app.workers.settings.WorkerSettings"]
    env_file: .env
    environment:
      NEO4J_URI: bolt://neo4j:7687
      REDIS_URL: redis://:${REDIS_PASSWORD:-worldrag}@redis:6379
      POSTGRES_URI: postgresql://${POSTGRES_USER:-worldrag}:${POSTGRES_PASSWORD:-worldrag}@postgres:5432/${POSTGRES_DB:-worldrag}
    depends_on:
      neo4j:
        condition: service_healthy
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    mem_limit: 4g
    healthcheck:
      test: ["CMD", "python", "-c", "import redis; r=redis.from_url('redis://:${REDIS_PASSWORD:-worldrag}@redis:6379'); r.ping()"]
      interval: 30s
      timeout: 5s
      retries: 3

  frontend:
    build:
      context: ./frontend
      target: dev
    restart: unless-stopped
    ports:
      - "${BIND_HOST:-127.0.0.1}:3000:3000"
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.next
    environment:
      BACKEND_URL: http://backend:8000
    depends_on:
      backend:
        condition: service_healthy

volumes:
  neo4j_data:
  redis_data:
  postgres_data:
```

Key changes vs old:
- LangFuse + langfuse-db **removed** (2 services, 1 volume gone)
- Frontend service **added** (dev target, volume mounts, proxy config)
- All ports use `${BIND_HOST:-127.0.0.1}` (configurable for VPS)
- Worker gets **healthcheck**
- Backend/worker no longer set `LANGFUSE_HOST`
- No more `langfuse_pgdata` volume

**Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(deploy): simplified 6-service compose, remove LangFuse, add frontend"
```

---

### Task 6: Clean up .env.example and backend config

**Files:**
- Rewrite: `.env.example`
- Modify: `backend/app/config.py` (line 70 — langfuse_host default, line 79 — cors_origins)
- Modify: `backend/app/main.py` (lines 97–111 — LangFuse init section)

**Step 1: Rewrite .env.example with documentation**

```env
# ═══════════════════════════════════════════════════════════════════════
# WorldRAG Configuration
# ═══════════════════════════════════════════════════════════════════════
# Copy to .env and fill in your API keys.
# All infrastructure defaults work out of the box with docker compose up.

# ── Infrastructure ──────────────────────────────────────────────────
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=worldrag
REDIS_PASSWORD=worldrag
REDIS_URL=redis://:worldrag@localhost:6379
POSTGRES_USER=worldrag
POSTGRES_PASSWORD=worldrag
POSTGRES_DB=worldrag
POSTGRES_URI=postgresql://worldrag:worldrag@localhost:5432/worldrag

# Network binding (127.0.0.1 for local dev, 0.0.0.0 for VPS)
BIND_HOST=127.0.0.1

# ── LLM Providers ──────────────────────────────────────────────────
# At least one provider key is required for extraction.
GEMINI_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# ── LLM Model Selection ────────────────────────────────────────────
LANGEXTRACT_MODEL=gemini-2.5-flash
LLM_RECONCILIATION=gemini:gemini-2.5-flash
LLM_CLASSIFICATION=gemini:gemini-2.5-flash
LLM_DEDUP=gemini:gemini-2.5-flash
LLM_CYPHER=gemini:gemini-2.5-flash
LLM_CHAT=gemini:gemini-2.5-flash
USE_BATCH_API=true

# ── Extraction Tuning ──────────────────────────────────────────────
LANGEXTRACT_PASSES=2
LANGEXTRACT_MAX_WORKERS=20
LANGEXTRACT_BATCH_CHAPTERS=10
LANGEXTRACT_MAX_CHAR_BUFFER=2000
COST_CEILING_PER_CHAPTER=0.50
COST_CEILING_PER_BOOK=50.00

# ── Embedding ──────────────────────────────────────────────────────
VOYAGE_API_KEY=
EMBEDDING_MODEL=voyage-3.5
EMBEDDING_BATCH_SIZE=128
EMBEDDING_DEVICE=cpu

# ── Application ────────────────────────────────────────────────────
CORS_ORIGINS=http://localhost:3000
LOG_LEVEL=INFO
LOG_FORMAT=json

# ── LangFuse (optional, leave empty to disable) ───────────────────
LANGFUSE_HOST=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

**Step 2: Make LangFuse init properly conditional**

In `backend/app/config.py` line 70, change default to empty:

```python
# OLD (line 70)
langfuse_host: str = "http://localhost:3001"

# NEW
langfuse_host: str = ""
```

In `backend/app/main.py`, the LangFuse init block (around lines 97–111) already checks for keys:
```python
if settings.langfuse_public_key and settings.langfuse_secret_key:
```
Add host check too:
```python
if settings.langfuse_host and settings.langfuse_public_key and settings.langfuse_secret_key:
```

**Step 3: Lint**

```bash
uv run ruff check backend/app/config.py backend/app/main.py --fix
```

**Step 4: Commit**

```bash
git add .env.example backend/app/config.py backend/app/main.py
git commit -m "feat(deploy): documented .env.example, LangFuse optional, clean defaults"
```

---

### Task 7: Verify full stack

**Step 1: Stop everything currently running**

```bash
# Kill any local processes on 8001, 3500, etc.
docker compose down -v  # remove old volumes for clean state
```

**Step 2: Start fresh**

```bash
docker compose up --build
```

Wait for all services to be healthy.

**Step 3: Verify health**

```bash
curl http://localhost:8000/api/health
# Expected: {"status":"healthy","services":{"neo4j":"ok","redis":"ok","postgres":"ok"}}

curl -s http://localhost:3000 | head -5
# Expected: HTML from Next.js

curl http://localhost:3000/api/books
# Expected: [] (empty array, proxied through Next.js to backend)
```

**Step 4: Verify Neo4j auto-init**

```bash
docker compose logs backend | grep neo4j_schema
# Expected: "neo4j_schema_initialized" with statements count
```

**Step 5: Verify Neo4j browser**

Open http://localhost:7474, run `SHOW CONSTRAINTS` — should show 21 constraints.

**Step 6: Commit any fixes if needed**

```bash
git add -A
git commit -m "fix(deploy): adjustments from full-stack verification"
```

---

### Task 8: Cleanup

**Files:**
- Delete: `frontend/.env.local` (if still exists)
- Verify: `.gitignore` covers `.env`

**Step 1: Remove stale files**

```bash
rm -f frontend/.env.local
```

**Step 2: Final lint + type-check**

```bash
uv run ruff check backend/ --fix
uv run ruff format backend/
cd frontend && npx tsc --noEmit
```

**Step 3: Final commit**

```bash
git add -A
git commit -m "chore(deploy): cleanup stale env files, final lint pass"
```
