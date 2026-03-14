# KG v2 Wiring — API Endpoints, ChatService Switch, Leiden, Saga Profiles

**Design Spec**
*2026-03-14 — Nicolas, LIFAT / Université de Tours*

---

## 1. Goal

Wire the remaining pieces to make the KG v2 pipeline (Graphiti + SagaProfileInducer) fully operational end-to-end: API endpoints for triggering ingestion, chat service switch, saga profile management, and community clustering.

---

## 2. Endpoint: POST /books/{book_id}/extract-graphiti

**File:** `backend/app/api/routes/books.py`

New endpoint alongside the existing `/books/{book_id}/extract`. Enqueues `process_book_graphiti` arq job.

```
POST /api/books/{book_id}/extract-graphiti
Body: {
  "saga_id": "primal-hunter",
  "saga_name": "The Primal Hunter",
  "book_num": 1
}
Response 202: { "job_id": "graphiti:book-1", "mode": "discovery" | "guided" }
```

**Logic:**
1. Check if SagaProfile exists in Redis (`saga_profile:{saga_id}`)
2. If exists → enqueue with `saga_profile_json` (Guided Mode)
3. If not → enqueue without (Discovery Mode)
4. Return job_id and mode

**Auth:** `require_auth` (same as existing extract endpoint).

---

## 3. ChatService v2 Switch

**Files:**
- Create: `backend/app/services/chat_service_v2.py`
- Modify: `backend/app/api/routes/chat.py`

### ChatServiceV2

Thin wrapper around `build_chat_v2_graph()`, same interface as `ChatService`:

```python
class ChatServiceV2:
    def __init__(self, graphiti: GraphitiClient, neo4j_driver: AsyncDriver, checkpointer=None):
        graph = build_chat_v2_graph(graphiti=graphiti, neo4j_driver=neo4j_driver)
        self._graph = graph.compile(checkpointer=checkpointer)

    async def query(self, query, book_id, saga_id, ...) -> ChatResponse:
        # invoke graph, map result to ChatResponse

    async def query_stream(self, query, book_id, saga_id, ...) -> AsyncGenerator:
        # stream graph, yield SSE events
```

### Route switch

In `chat.py`, check `settings.graphiti_enabled`:
- If True → instantiate `ChatServiceV2(graphiti, neo4j_driver, checkpointer)`
- If False → instantiate `ChatService(neo4j_driver, checkpointer)` (current behavior)

The chat endpoints (`POST /chat/query`, `GET /chat/stream`) don't change their API — only the backing service switches.

---

## 4. Saga Profiles API

**File:** Create `backend/app/api/routes/saga_profiles.py`

```
GET  /api/saga-profiles              → list all saga profiles (keys from Redis)
GET  /api/saga-profiles/{saga_id}    → return SagaProfile JSON
PUT  /api/saga-profiles/{saga_id}    → update profile (full replace)
DELETE /api/saga-profiles/{saga_id}  → delete profile
```

**Storage:** Redis keys `saga_profile:{saga_id}`. SagaProfile serialized as JSON.

**Schemas:**
- Response: `SagaProfileResponse` (wraps SagaProfile + metadata)
- Request (PUT): `SagaProfileUpdateRequest` (full SagaProfile body)

**Auth:** `require_auth` for all endpoints.

**Register:** Add router in `main.py` → `app.include_router(saga_profiles.router, prefix="/api")`.

---

## 5. Leiden Community Clustering

**File:** Create `backend/app/services/community_clustering.py`

Post-processing step after Graphiti ingestion:

1. **Project graph** via Neo4j GDS:
   ```cypher
   CALL gds.graph.project('saga-graph', 'Entity', 'RELATES_TO',
     { nodeProperties: ['group_id'], relationshipProperties: [] })
   ```

2. **Run Leiden**:
   ```cypher
   CALL gds.leiden.write('saga-graph', { writeProperty: 'community_id' })
   ```

3. **Generate community summaries**:
   - For each community_id, fetch member entities
   - LLM call: "Summarize this group of entities from a fiction novel: [names + summaries]"
   - Store as `:Community {community_id, summary, saga_id}` nodes in Neo4j

4. **Cleanup**: Drop GDS projection

**Integration:** Called at the end of `process_book_graphiti` worker task, after ingestion completes.

**Fallback:** If GDS is unavailable (Community edition limitation), use Python `leidenalg` library on exported adjacency matrix.

---

## 6. Infrastructure Changes

- `backend/app/main.py`: Register `saga_profiles.router`
- `backend/app/api/routes/__init__.py`: Export new router (if applicable)
- `backend/app/schemas/saga_profile.py`: API request/response schemas
- No Docker changes needed (GDS already added in T11)

---

## 7. New Files

| File | Role |
|---|---|
| `backend/app/api/routes/saga_profiles.py` | CRUD endpoints for saga profiles |
| `backend/app/schemas/saga_profile.py` | API schemas (response/request wrappers) |
| `backend/app/services/chat_service_v2.py` | ChatServiceV2 using chat_v2 graph |
| `backend/app/services/community_clustering.py` | Leiden + LLM community summaries |

## 8. Modified Files

| File | Changes |
|---|---|
| `backend/app/api/routes/books.py` | Add extract-graphiti endpoint |
| `backend/app/api/routes/chat.py` | Switch service based on graphiti_enabled |
| `backend/app/main.py` | Register saga_profiles router |
| `backend/app/workers/tasks.py` | Call community_clustering after ingestion |
