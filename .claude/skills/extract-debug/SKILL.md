---
name: extract-debug
description: Debug extraction pipeline issues — inspect DLQ, cost tracking, failed chapters, arq worker state
disable-model-invocation: true
---

# Extraction Pipeline Debugger

Diagnose and resolve extraction pipeline issues in WorldRAG.

## Workflow

### 1. Assess the situation

Ask the user what they're seeing (or infer from context):
- Extraction stuck / not progressing
- Chapters failing silently
- Cost ceiling hit
- Entity extraction quality issues
- Worker not picking up jobs

### 2. Check infrastructure health

```bash
# Docker services running?
docker compose -f E:/RAG/docker-compose.yml ps

# Redis connectivity (arq queue backend)
docker exec rag-redis-1 redis-cli -a worldrag ping

# Neo4j connectivity
docker exec rag-neo4j-1 cypher-shell -u neo4j -p worldrag "RETURN 1 AS test"

# Backend API health
curl -s http://localhost:8000/api/health
```

### 3. Inspect the DLQ (Dead Letter Queue)

The DLQ stores failed chapter extractions. Key files:
- `backend/app/core/dead_letter.py` — `DeadLetterQueue` class (Redis key: `worldrag:dlq:extraction`)
- `backend/app/api/routes/admin.py` — Admin endpoints

```bash
# List all DLQ entries
curl -s http://localhost:8000/api/admin/dlq | python -m json.tool

# DLQ size
curl -s http://localhost:8000/api/admin/dlq/size

# Filter by book
curl -s "http://localhost:8000/api/admin/dlq?book_id=BOOK_ID" | python -m json.tool
```

For each DLQ entry, check:
- `error_type`: CostCeilingError, LLM rate limit, Neo4j connection, schema validation
- `error_message`: The actual error
- `attempt_count`: How many retries have been attempted
- `metadata.genre`, `metadata.pipeline`: Which pipeline version was used

### 4. Inspect cost tracking

```bash
# Aggregated cost summary
curl -s http://localhost:8000/api/admin/costs | python -m json.tool

# Cost breakdown for a specific book
curl -s http://localhost:8000/api/admin/costs/BOOK_ID | python -m json.tool
```

Key thresholds (from `backend/app/core/cost_tracker.py`):
- `ceiling_per_chapter`: $0.50 default
- `ceiling_per_book`: $50.00 default

If cost ceiling was hit, the book status will be `cost_ceiling_hit`. Options:
1. Adjust ceilings in config and retry
2. Retry individual chapters via DLQ

### 5. Check arq worker state

```bash
# Check if worker process is running
tasklist | grep -i python

# Check Redis queue length
docker exec rag-redis-1 redis-cli -a worldrag LLEN worldrag:arq:queue
docker exec rag-redis-1 redis-cli -a worldrag LLEN arq:queue:worldrag:arq

# Check pending/active jobs
docker exec rag-redis-1 redis-cli -a worldrag KEYS "arq:*"
```

Worker tasks are in `backend/app/workers/tasks.py`:
- `process_book_extraction` — Main extraction (delegates to v3)
- `process_book_extraction_v3` — 6-phase pipeline with EntityRegistry
- `process_book_embeddings` — VoyageAI batch embedding (auto-chained after extraction)
- `process_book_reprocessing` — Selective re-extraction

### 6. Check book/chapter status in Neo4j

```bash
# Book status
docker exec rag-neo4j-1 cypher-shell -u neo4j -p worldrag \
  "MATCH (b:Book) RETURN b.title, b.status, b.chapters_processed, b.entity_count ORDER BY b.created_at DESC"

# Chapters with extraction status
docker exec rag-neo4j-1 cypher-shell -u neo4j -p worldrag \
  "MATCH (b:Book {id: 'BOOK_ID'})-[:HAS_CHAPTER]->(c:Chapter) RETURN c.number, c.title, c.status ORDER BY c.number"

# Find chapters without entities (potentially failed silently)
docker exec rag-neo4j-1 cypher-shell -u neo4j -p worldrag \
  "MATCH (b:Book {id: 'BOOK_ID'})-[:HAS_CHAPTER]->(c:Chapter) WHERE c.status <> 'extracted' RETURN c.number, c.title, c.status ORDER BY c.number"
```

### 7. Retry failed chapters

```bash
# Retry a single chapter
curl -X POST http://localhost:8000/api/admin/dlq/retry/BOOK_ID/CHAPTER_NUM

# Retry all failed chapters
curl -X POST http://localhost:8000/api/admin/dlq/retry-all

# Clear the DLQ (use with caution)
curl -X POST http://localhost:8000/api/admin/dlq/clear
```

### 8. LangGraph extraction debugging

The extraction graph runs 4 parallel passes (route → [characters|systems|events|lore] → merge → reconcile).

Key files to inspect:
- `backend/app/services/extraction/__init__.py` — Main orchestrator, `extract_chapter()` / `extract_chapter_v3()`
- `backend/app/services/extraction/router.py` — Keyword-based pass routing
- `backend/app/services/extraction/reconciler.py` — 3-tier dedup (exact → fuzzy → LLM)
- `backend/app/services/graph_builder.py` — `build_book_graph()`, `build_chapter_graph()`
- `backend/app/agents/state.py` — `ExtractionPipelineState`

If entities are missing or wrong:
1. Check router keywords (is the relevant pass being triggered?)
2. Check reconciler alias_map (are entities being merged incorrectly?)
3. Check LangFuse traces at http://localhost:3001 for LLM call details
