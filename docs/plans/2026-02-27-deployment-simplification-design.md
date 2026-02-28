# WorldRAG Deployment Simplification Design

**Date**: 2026-02-27
**Status**: Approved
**Goal**: One `docker compose up` launches the full stack, robustly, on dev and VPS.

## Context

The current setup requires 4+ manual terminal windows, has port conflicts on Windows (Hyper-V excluded ranges), hardcoded localhost URLs in CSP headers, LangFuse adding 2 unnecessary containers, a frontend not in Docker, and no automatic Neo4j schema init.

## Design

### Architecture: 6 Services

```
docker compose up
├── neo4j        :7474/:7687
├── redis        :6379
├── postgres     :5432
├── backend      :8000  (FastAPI + auto init Neo4j schema)
├── worker       (arq extraction + embedding jobs)
└── frontend     :3000  (Next.js, proxied API via rewrites)
```

**Removed**: langfuse, langfuse-db (2 containers + 1 volume).

### Frontend Proxy (eliminates CORS/CSP/port mismatch)

`next.config.ts` adds `rewrites()`:
```ts
async rewrites() {
  return [{ source: '/api/:path*', destination: 'http://backend:8000/api/:path*' }]
}
```

- `API_BASE` becomes `/api` (same-origin, no CORS needed)
- CSP simplified to `connect-src 'self'`
- SSE streaming works through the proxy
- `frontend/.env.local` deleted (no more port config)

### Environment Configuration

Single `.env` at project root (gitignored), documented `.env.example`:

```env
# Infrastructure
NEO4J_PASSWORD=worldrag
REDIS_PASSWORD=worldrag
POSTGRES_USER=worldrag
POSTGRES_PASSWORD=worldrag
POSTGRES_DB=worldrag
BIND_HOST=127.0.0.1          # 0.0.0.0 for VPS

# LLM Providers (required)
GEMINI_API_KEY=               # https://aistudio.google.com/apikey

# LLM Models
LANGEXTRACT_MODEL=gemini-2.5-flash
LLM_RECONCILIATION=gemini:gemini-2.5-flash
# ...
```

### Dockerfiles

**Backend (improved)**:
- Non-root user `worldrag` (uid 1000)
- Healthcheck via `curl` instead of Python urllib
- `scripts/init_neo4j.cypher` copied into image

**Frontend (new `frontend/Dockerfile`)**:
- Multi-stage: `node:22-alpine`
- `target: dev` for development (npm run dev + volume mount)
- `target: prod` for production (npm run build + npm start)
- Anonymous volumes for `node_modules` and `.next` cache

### Auto-Init Neo4j Schema

In backend `lifespan` startup:
1. `SHOW CONSTRAINTS` — if count > 0, skip
2. Otherwise, read and execute `init_neo4j.cypher`
3. Log result

Eliminates manual `docker exec` step.

### Worker Healthcheck

```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import redis; r=redis.from_url('$REDIS_URL'); r.ping()"]
  interval: 30s
  timeout: 5s
  retries: 3
```

### LangFuse Cleanup

- Remove `langfuse` + `langfuse-db` services from docker-compose
- Remove `langfuse_pgdata` volume
- Make LangFuse init conditional in `main.py` (already checks for keys)
- Keep instrumentation code (no-op when unconfigured)
- Remove LangFuse env vars from `.env.example`

### Security

- `.env` gitignored (already the case)
- Backend runs as non-root user
- CSP: remove `unsafe-eval`, simplify `connect-src` to `'self'`
- Ports configurable via `BIND_HOST` (127.0.0.1 default, 0.0.0.0 for VPS)

### What Does NOT Change

- Backend code (routes, services, repos)
- Frontend components and pages
- Neo4j schema
- Extraction pipeline logic
- SSE streaming (works via proxy)
