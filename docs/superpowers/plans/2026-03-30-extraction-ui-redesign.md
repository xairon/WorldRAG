# Extraction UI Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat extraction dashboard with a guided 5-step pipeline (Upload → Configure → Extract → Review → Explore), add TanStack Query + SSE reconnection + shared components, and create 4 backend endpoints for entity/relation editing.

**Architecture:** Backend-first (4 CRUD endpoints on Neo4j), then frontend infra (TanStack Query, SSE hook, shared components), then pipeline steps (Upload → Configure → Extract → Review → Explore). Each task produces testable, committable work.

**Tech Stack:** Python/FastAPI (backend), Next.js 16 / React 19 / TypeScript / Tailwind 4 / shadcn/ui (frontend), TanStack Query v5, nuqs v2, motion (framer-motion)

**Spec:** `docs/superpowers/specs/2026-03-30-extraction-ui-redesign.md`

---

## File Structure

### Backend (2 files modified/created)

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `backend/app/api/routes/graph.py` | Add 4 endpoints: PATCH entity, DELETE entity, POST merge, DELETE relationship |
| Create | `backend/tests/api/test_graph_mutations.py` | Tests for the 4 new endpoints |

### Frontend (22 files created, 3 modified, 4 deleted)

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `frontend/lib/query-client.ts` | QueryClient singleton + QueryProvider wrapper |
| Create | `frontend/hooks/use-books.ts` | TanStack Query hooks for book data |
| Create | `frontend/hooks/use-extraction.ts` | SSE hook with reconnection + extraction mutations |
| Create | `frontend/hooks/use-graph-mutations.ts` | TanStack Query mutations for entity/relation CRUD |
| Create | `frontend/components/pipeline/step-indicator.tsx` | 5-step progress bar |
| Create | `frontend/components/pipeline/pipeline-layout.tsx` | Pipeline wrapper with StepIndicator + step transitions |
| Create | `frontend/components/ui/error-state.tsx` | Error display with retry button |
| Create | `frontend/components/ui/confidence-bar.tsx` | Colored confidence bar (0-1) |
| Create | `frontend/components/ui/sse-indicator.tsx` | Connection status dot |
| Create | `frontend/components/extraction/steps/upload-step.tsx` | Drag & drop upload + book list |
| Create | `frontend/components/extraction/steps/configure-step.tsx` | Genre, language, provider selection |
| Create | `frontend/components/extraction/steps/extract-step.tsx` | Real-time progress with 2-column layout |
| Create | `frontend/components/extraction/steps/review-step.tsx` | Post-extraction review with 3 tabs |
| Create | `frontend/components/extraction/steps/explore-step.tsx` | CTA to graph explorer + exports |
| Create | `frontend/components/extraction/chapter-progress-list.tsx` | Scrollable chapter rows with status |
| Create | `frontend/components/extraction/extraction-live-stats.tsx` | Stats panel with donut + counters |
| Create | `frontend/components/extraction/review/entity-review-table.tsx` | Editable entity table |
| Create | `frontend/components/extraction/review/relation-review-table.tsx` | Relation table with delete |
| Create | `frontend/components/extraction/review/problems-panel.tsx` | DLQ + duplicates + orphans |
| Modify | `frontend/app/layout.tsx` | Wrap with QueryClientProvider |
| Modify | `frontend/app/projects/[slug]/books/[bookId]/extraction/page.tsx` | Pipeline container with URL state |
| Modify | `frontend/package.json` | Add @tanstack/react-query, nuqs; remove swr |
| Delete | `frontend/app/projects/[slug]/books/[bookId]/extraction/dashboard.tsx` | Replaced by pipeline steps |
| Delete | `frontend/hooks/use-extraction-stream.ts` | Replaced by use-extraction.ts |
| Delete | `frontend/stores/extraction-store.ts` | State moved to TanStack Query + SSE hook |
| Delete | `frontend/stores/graph-store.ts` | Unused |

---

### Task 1: Backend — Entity/Relation CRUD endpoints

**Files:**
- Modify: `backend/app/api/routes/graph.py`
- Create: `backend/tests/api/test_graph_mutations.py`

- [ ] **Step 1: Write tests for the 4 endpoints**

```python
"""Tests for graph mutation endpoints (entity CRUD, merge, relation delete)."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_neo4j_session():
    session = AsyncMock()
    result = AsyncMock()
    result.single = AsyncMock()
    result.data = AsyncMock(return_value=[])
    summary = MagicMock()
    summary.counters.nodes_deleted = 1
    summary.counters.relationships_deleted = 0
    result.consume = AsyncMock(return_value=summary)
    session.run = AsyncMock(return_value=result)
    return session


@pytest.fixture
def mock_neo4j_driver(mock_neo4j_session):
    driver = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_neo4j_session)
    cm.__aexit__ = AsyncMock(return_value=False)
    driver.session.return_value = cm
    return driver


class TestPatchEntity:
    @pytest.mark.asyncio
    async def test_rename_entity(self, mock_neo4j_driver, mock_neo4j_session):
        from app.api.routes.graph import update_entity

        mock_neo4j_session.run.return_value.single.return_value = {
            "id": "4:abc:123",
            "labels": ["Character"],
            "props": {"name": "Jake Thayne", "canonical_name": "jake thayne"},
        }
        result = await update_entity(
            entity_id="4:abc:123",
            body={"name": "Jake Thayne", "canonical_name": "jake thayne"},
            driver=mock_neo4j_driver,
        )
        assert result["id"] == "4:abc:123"
        assert "name" in result["updated_properties"]

    @pytest.mark.asyncio
    async def test_update_no_fields_returns_400(self, mock_neo4j_driver):
        from app.api.routes.graph import update_entity
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await update_entity(
                entity_id="4:abc:123",
                body={},
                driver=mock_neo4j_driver,
            )
        assert exc_info.value.status_code == 400


class TestDeleteEntity:
    @pytest.mark.asyncio
    async def test_delete_existing_entity(self, mock_neo4j_driver, mock_neo4j_session):
        from app.api.routes.graph import delete_entity

        # First call: count rels, second call: detach delete
        count_result = AsyncMock()
        count_result.single.return_value = {"rel_count": 3}
        delete_result = AsyncMock()
        delete_summary = MagicMock()
        delete_summary.counters.nodes_deleted = 1
        delete_result.consume = AsyncMock(return_value=delete_summary)
        mock_neo4j_session.run = AsyncMock(side_effect=[count_result, delete_result])

        result = await delete_entity(entity_id="4:abc:123", driver=mock_neo4j_driver)
        assert result["deleted"] is True
        assert result["relationships_removed"] == 3


class TestMergeEntities:
    @pytest.mark.asyncio
    async def test_merge_transfers_relationships(self, mock_neo4j_driver, mock_neo4j_session):
        from app.api.routes.graph import merge_entities

        # Mock: source entity exists with aliases
        source_result = AsyncMock()
        source_result.single.return_value = {
            "name": "Jacob",
            "aliases": ["Jake"],
        }
        # Mock: target entity exists
        target_result = AsyncMock()
        target_result.single.return_value = {
            "name": "Jake Thayne",
            "aliases": ["Jake T"],
        }
        # Mock: relationship queries + delete
        rel_result = AsyncMock()
        rel_result.data.return_value = []
        summary_result = AsyncMock()
        summary = MagicMock()
        summary.counters.nodes_deleted = 1
        summary.counters.relationships_deleted = 0
        summary_result.consume = AsyncMock(return_value=summary)
        update_result = AsyncMock()

        mock_neo4j_session.run = AsyncMock(
            side_effect=[source_result, target_result, update_result, rel_result, rel_result, summary_result]
        )

        result = await merge_entities(
            body={"source_id": "4:abc:1", "target_id": "4:abc:2"},
            driver=mock_neo4j_driver,
        )
        assert result["merged_into"] == "4:abc:2"

    @pytest.mark.asyncio
    async def test_merge_same_id_returns_400(self, mock_neo4j_driver):
        from app.api.routes.graph import merge_entities
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await merge_entities(
                body={"source_id": "4:abc:1", "target_id": "4:abc:1"},
                driver=mock_neo4j_driver,
            )
        assert exc_info.value.status_code == 400


class TestDeleteRelationship:
    @pytest.mark.asyncio
    async def test_delete_existing_relationship(self, mock_neo4j_driver, mock_neo4j_session):
        from app.api.routes.graph import delete_relationship

        result_mock = AsyncMock()
        summary = MagicMock()
        summary.counters.relationships_deleted = 1
        result_mock.consume = AsyncMock(return_value=summary)
        mock_neo4j_session.run = AsyncMock(return_value=result_mock)

        result = await delete_relationship(relationship_id="5:abc:99", driver=mock_neo4j_driver)
        assert result["deleted"] is True

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, mock_neo4j_driver, mock_neo4j_session):
        from app.api.routes.graph import delete_relationship
        from fastapi import HTTPException

        result_mock = AsyncMock()
        summary = MagicMock()
        summary.counters.relationships_deleted = 0
        result_mock.consume = AsyncMock(return_value=summary)
        mock_neo4j_session.run = AsyncMock(return_value=result_mock)

        with pytest.raises(HTTPException) as exc_info:
            await delete_relationship(relationship_id="5:abc:99", driver=mock_neo4j_driver)
        assert exc_info.value.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/ringuet/WorldRAG && uv run pytest backend/tests/api/test_graph_mutations.py -v`
Expected: ImportError — functions don't exist yet

- [ ] **Step 3: Implement the 4 endpoints**

Add to the end of `backend/app/api/routes/graph.py`:

```python
# ── Entity / Relationship mutations ──────────────────────────────────────


@router.patch("/entity/{entity_id}", dependencies=[Depends(require_auth)])
async def update_entity(
    entity_id: str,
    body: dict,
    driver: AsyncDriver = Depends(get_neo4j),
) -> dict:
    """Rename or update an entity's properties."""
    allowed_fields = {"name", "canonical_name", "description"}
    updates = {k: v for k, v in body.items() if k in allowed_fields and v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    set_clause = ", ".join(f"e.{k} = ${k}" for k in updates)
    cypher = f"MATCH (e) WHERE elementId(e) = $id SET {set_clause} RETURN elementId(e) AS id, labels(e) AS labels, properties(e) AS props"
    params = {"id": entity_id, **updates}

    async with driver.session() as session:
        result = await session.run(cypher, params)
        record = await result.single()
        if not record:
            raise HTTPException(status_code=404, detail="Entity not found")

    logger.info("entity_updated", entity_id=entity_id, fields=list(updates.keys()))
    return {
        "id": record["id"],
        "labels": record["labels"],
        "updated_properties": list(updates.keys()),
    }


@router.delete("/entity/{entity_id}", dependencies=[Depends(require_auth)])
async def delete_entity(
    entity_id: str,
    driver: AsyncDriver = Depends(get_neo4j),
) -> dict:
    """Delete an entity and all its relationships."""
    async with driver.session() as session:
        # Count relationships first
        count_result = await session.run(
            "MATCH (e)-[r]-() WHERE elementId(e) = $id RETURN count(r) AS rel_count",
            {"id": entity_id},
        )
        count_record = await count_result.single()
        rel_count = count_record["rel_count"] if count_record else 0

        # Detach delete
        delete_result = await session.run(
            "MATCH (e) WHERE elementId(e) = $id DETACH DELETE e",
            {"id": entity_id},
        )
        summary = await delete_result.consume()
        if summary.counters.nodes_deleted == 0:
            raise HTTPException(status_code=404, detail="Entity not found")

    logger.info("entity_deleted", entity_id=entity_id, relationships_removed=rel_count)
    return {"deleted": True, "relationships_removed": rel_count}


@router.post("/entities/merge", dependencies=[Depends(require_auth)])
async def merge_entities(
    body: dict,
    driver: AsyncDriver = Depends(get_neo4j),
) -> dict:
    """Merge source entity into target: transfer relationships, merge aliases, delete source."""
    source_id = body.get("source_id", "")
    target_id = body.get("target_id", "")
    if not source_id or not target_id:
        raise HTTPException(status_code=400, detail="source_id and target_id required")
    if source_id == target_id:
        raise HTTPException(status_code=400, detail="Cannot merge entity with itself")

    async with driver.session() as session:
        # 1. Read source
        src_result = await session.run(
            "MATCH (e) WHERE elementId(e) = $id "
            "RETURN e.name AS name, coalesce(e.aliases, []) AS aliases",
            {"id": source_id},
        )
        src = await src_result.single()
        if not src:
            raise HTTPException(status_code=404, detail="Source entity not found")

        # 2. Read target
        tgt_result = await session.run(
            "MATCH (e) WHERE elementId(e) = $id "
            "RETURN e.name AS name, coalesce(e.aliases, []) AS aliases",
            {"id": target_id},
        )
        tgt = await tgt_result.single()
        if not tgt:
            raise HTTPException(status_code=404, detail="Target entity not found")

        # 3. Merge aliases: add source name + source aliases to target
        new_aliases = [src["name"]] + list(src["aliases"])
        existing = set(tgt["aliases"])
        added = [a for a in new_aliases if a and a not in existing and a != tgt["name"]]
        if added:
            await session.run(
                "MATCH (e) WHERE elementId(e) = $id "
                "SET e.aliases = coalesce(e.aliases, []) + $added",
                {"id": target_id, "added": added},
            )

        # 4. Transfer relationships (read all rels from source, recreate on target)
        # Outgoing
        out_result = await session.run(
            "MATCH (s)-[r]->(other) WHERE elementId(s) = $id "
            "RETURN type(r) AS rel_type, elementId(other) AS other_id, properties(r) AS props",
            {"id": source_id},
        )
        out_rels = await out_result.data()

        # Incoming
        in_result = await session.run(
            "MATCH (other)-[r]->(s) WHERE elementId(s) = $id "
            "RETURN type(r) AS rel_type, elementId(other) AS other_id, properties(r) AS props",
            {"id": source_id},
        )
        in_rels = await in_result.data()

        transferred = 0
        for rel in out_rels:
            if rel["other_id"] == target_id:
                continue  # skip self-loops
            await session.run(
                f"MATCH (t), (o) WHERE elementId(t) = $tid AND elementId(o) = $oid "
                f"CREATE (t)-[r:`{rel['rel_type']}`]->(o) SET r = $props",
                {"tid": target_id, "oid": rel["other_id"], "props": rel["props"] or {}},
            )
            transferred += 1

        for rel in in_rels:
            if rel["other_id"] == target_id:
                continue
            await session.run(
                f"MATCH (o), (t) WHERE elementId(o) = $oid AND elementId(t) = $tid "
                f"CREATE (o)-[r:`{rel['rel_type']}`]->(t) SET r = $props",
                {"oid": rel["other_id"], "tid": target_id, "props": rel["props"] or {}},
            )
            transferred += 1

        # 5. Delete source
        await session.run(
            "MATCH (e) WHERE elementId(e) = $id DETACH DELETE e",
            {"id": source_id},
        )

    logger.info(
        "entities_merged",
        source_id=source_id,
        target_id=target_id,
        aliases_added=added,
        relationships_transferred=transferred,
    )
    return {
        "merged_into": target_id,
        "aliases_added": added,
        "relationships_transferred": transferred,
    }


@router.delete("/relationship/{relationship_id}", dependencies=[Depends(require_auth)])
async def delete_relationship(
    relationship_id: str,
    driver: AsyncDriver = Depends(get_neo4j),
) -> dict:
    """Delete a single relationship by element ID."""
    async with driver.session() as session:
        result = await session.run(
            "MATCH ()-[r]->() WHERE elementId(r) = $id DELETE r",
            {"id": relationship_id},
        )
        summary = await result.consume()
        if summary.counters.relationships_deleted == 0:
            raise HTTPException(status_code=404, detail="Relationship not found")

    logger.info("relationship_deleted", relationship_id=relationship_id)
    return {"deleted": True}
```

- [ ] **Step 4: Run tests**

Run: `cd /home/ringuet/WorldRAG && uv run pytest backend/tests/api/test_graph_mutations.py -v`
Expected: All tests PASS

- [ ] **Step 5: Lint**

Run: `cd /home/ringuet/WorldRAG && uv run ruff check backend/app/api/routes/graph.py backend/tests/api/test_graph_mutations.py --fix && uv run ruff format backend/app/api/routes/graph.py backend/tests/api/test_graph_mutations.py`

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/routes/graph.py backend/tests/api/test_graph_mutations.py
git commit -m "feat: add entity/relation CRUD endpoints (PATCH, DELETE, merge)"
```

---

### Task 2: Frontend — Install dependencies & QueryClientProvider

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/lib/query-client.ts`
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: Install dependencies**

Run: `cd /home/ringuet/WorldRAG/frontend && npm install @tanstack/react-query@^5 nuqs@^2 && npm uninstall swr`

- [ ] **Step 2: Create QueryClient provider**

Create `frontend/lib/query-client.ts`:

```typescript
"use client"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { useState } from "react"

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        retry: 3,
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30_000),
      },
    },
  })
}

let browserQueryClient: QueryClient | undefined

function getQueryClient() {
  if (typeof window === "undefined") {
    return makeQueryClient()
  }
  if (!browserQueryClient) {
    browserQueryClient = makeQueryClient()
  }
  return browserQueryClient
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(getQueryClient)
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}
```

- [ ] **Step 3: Wrap layout with Providers**

Replace `frontend/app/layout.tsx`:

```typescript
import type { Metadata } from "next"
import { ThemeProvider } from "next-themes"
import { Toaster } from "@/components/ui/sonner"
import { Providers } from "@/lib/query-client"
import "./globals.css"

export const metadata: Metadata = {
  title: "WorldRAG",
  description: "Knowledge Graph construction for fiction universes",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="bg-background text-foreground antialiased">
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem disableTransitionOnChange>
          <Providers>
            {children}
            <Toaster />
          </Providers>
        </ThemeProvider>
      </body>
    </html>
  )
}
```

- [ ] **Step 4: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/lib/query-client.ts frontend/app/layout.tsx
git commit -m "feat: add TanStack Query + nuqs, remove swr, wrap layout with QueryClientProvider"
```

---

### Task 3: Frontend — TanStack Query hooks for books

**Files:**
- Create: `frontend/hooks/use-books.ts`

- [ ] **Step 1: Create the hooks file**

```typescript
"use client"

import { useQuery } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api/client"
import type { BookInfo, BookDetail } from "@/lib/api/types"

export function useBooks(projectSlug: string | null) {
  return useQuery({
    queryKey: ["books", projectSlug],
    queryFn: () => apiFetch<BookInfo[]>(`/projects/${projectSlug}/books`),
    enabled: !!projectSlug,
    staleTime: 30_000,
  })
}

export function useBookDetail(bookId: string | null) {
  return useQuery({
    queryKey: ["book", bookId],
    queryFn: () => apiFetch<BookDetail>(`/books/${bookId}`),
    enabled: !!bookId,
    staleTime: 30_000,
  })
}

export function useBookStats(bookId: string | null) {
  return useQuery({
    queryKey: ["book-stats", bookId],
    queryFn: () => apiFetch<Record<string, unknown>>(`/books/${bookId}/stats`),
    enabled: !!bookId,
    staleTime: 60_000,
  })
}

interface BookJobs {
  book_id: string
  book_status: string
  jobs: {
    extraction: { job_id: string; status: string }
    embedding: { job_id: string; status: string }
  }
}

export function useBookJobs(bookId: string | null, polling = false) {
  return useQuery({
    queryKey: ["book-jobs", bookId],
    queryFn: () => apiFetch<BookJobs>(`/books/${bookId}/jobs`),
    enabled: !!bookId,
    refetchInterval: polling ? 5_000 : false,
  })
}
```

- [ ] **Step 2: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/hooks/use-books.ts
git commit -m "feat: TanStack Query hooks for books (useBooks, useBookDetail, useBookStats, useBookJobs)"
```

---

### Task 4: Frontend — SSE hook with reconnection

**Files:**
- Create: `frontend/hooks/use-extraction.ts`

- [ ] **Step 1: Create the SSE + extraction hooks file**

```typescript
"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiFetch, API_BASE } from "@/lib/api/client"
import type { DLQEntry } from "@/lib/api/types"

// ── Types ──────────────────────────────────────────────────────────────

export type SSEStatus = "connecting" | "connected" | "reconnecting" | "disconnected"

export interface ChapterProgress {
  chapter: number
  status: "pending" | "extracting" | "done" | "failed"
  entities: number
  duration_ms?: number
  error?: string
}

interface ExtractionSSEState {
  sseStatus: SSEStatus
  chapters: Map<number, ChapterProgress>
  totalEntities: number
  chaptersTotal: number
  chaptersDone: number
  error: string | null
  isDone: boolean
}

// ── SSE Hook ───────────────────────────────────────────────────────────

export function useExtractionSSE(bookId: string | null): ExtractionSSEState & { connect: () => void; disconnect: () => void } {
  const queryClient = useQueryClient()
  const esRef = useRef<EventSource | null>(null)
  const retryCountRef = useRef(0)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const keepaliveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [sseStatus, setSseStatus] = useState<SSEStatus>("disconnected")
  const [chapters, setChapters] = useState<Map<number, ChapterProgress>>(new Map())
  const [totalEntities, setTotalEntities] = useState(0)
  const [chaptersTotal, setChaptersTotal] = useState(0)
  const [chaptersDone, setChaptersDone] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [isDone, setIsDone] = useState(false)

  const resetKeepalive = useCallback(() => {
    if (keepaliveTimerRef.current) clearTimeout(keepaliveTimerRef.current)
    keepaliveTimerRef.current = setTimeout(() => {
      // No event for 60s — reconnect
      esRef.current?.close()
      setSseStatus("reconnecting")
      scheduleReconnect()
    }, 60_000)
  }, [])

  const scheduleReconnect = useCallback(() => {
    const delay = Math.min(1000 * 2 ** retryCountRef.current, 30_000)
    retryCountRef.current += 1
    retryTimerRef.current = setTimeout(() => connectSSE(), delay)
  }, [bookId])

  const connectSSE = useCallback(() => {
    if (!bookId) return
    esRef.current?.close()

    const es = new EventSource(`${API_BASE}/stream/extraction/${bookId}`)
    esRef.current = es
    setSseStatus("connecting")
    setError(null)

    es.onopen = () => {
      setSseStatus("connected")
      retryCountRef.current = 0
      resetKeepalive()
    }

    es.addEventListener("started", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data)
        setChaptersTotal(data.total ?? 0)
        setChaptersDone(0)
        setIsDone(false)
        resetKeepalive()
      } catch { /* ignore parse errors */ }
    })

    es.addEventListener("progress", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data)
        resetKeepalive()

        if (data.chapter) {
          setChapters((prev) => {
            const next = new Map(prev)
            next.set(data.chapter, {
              chapter: data.chapter,
              status: data.status === "failed" ? "failed" : "done",
              entities: data.entities_found ?? 0,
              duration_ms: data.duration_ms,
              error: data.error_message,
            })
            return next
          })
        }

        if (data.chapters_done != null) setChaptersDone(data.chapters_done)
        if (data.entities_found != null) setTotalEntities(data.entities_found)
      } catch { /* ignore */ }
    })

    es.addEventListener("done", () => {
      setIsDone(true)
      setSseStatus("disconnected")
      es.close()
      queryClient.invalidateQueries({ queryKey: ["book"] })
      queryClient.invalidateQueries({ queryKey: ["book-jobs"] })
    })

    es.addEventListener("error", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data)
        setError(data.message ?? "Extraction stopped due to an error")
        setSseStatus("disconnected")
      } catch {
        // Connection error — try reconnecting
        setSseStatus("reconnecting")
        scheduleReconnect()
      }
      es.close()
    })

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) {
        setSseStatus("reconnecting")
        scheduleReconnect()
      }
    }
  }, [bookId, queryClient, resetKeepalive, scheduleReconnect])

  const disconnect = useCallback(() => {
    esRef.current?.close()
    esRef.current = null
    if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
    if (keepaliveTimerRef.current) clearTimeout(keepaliveTimerRef.current)
    setSseStatus("disconnected")
  }, [])

  useEffect(() => {
    return () => disconnect()
  }, [disconnect])

  return {
    sseStatus,
    chapters,
    totalEntities,
    chaptersTotal,
    chaptersDone,
    error,
    isDone,
    connect: connectSSE,
    disconnect,
  }
}

// ── Extraction mutations ──────────────────────────────────────────────

export function useTriggerExtraction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ bookId, chapters, provider, genre, language }: {
      bookId: string
      chapters?: number[]
      provider?: string
      genre?: string
      language?: string
    }) =>
      apiFetch(`/books/${bookId}/extract/v4`, {
        method: "POST",
        body: JSON.stringify({
          ...(chapters?.length ? { chapters } : {}),
          ...(provider ? { provider } : {}),
          ...(genre ? { genre } : {}),
          ...(language ? { language } : {}),
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["book-jobs"] })
    },
  })
}

export function useRetryChapter() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ bookId, chapter }: { bookId: string; chapter: number }) =>
      apiFetch(`/admin/dlq/retry/${bookId}/${chapter}`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dlq"] })
    },
  })
}

export function useDLQEntries(bookId: string | null) {
  return useQuery({
    queryKey: ["dlq", bookId],
    queryFn: () =>
      apiFetch<{ count: number; entries: DLQEntry[] }>(
        `/admin/dlq${bookId ? `?book_id=${bookId}` : ""}`
      ),
    enabled: !!bookId,
    staleTime: 10_000,
  })
}
```

- [ ] **Step 2: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build`

- [ ] **Step 3: Commit**

```bash
git add frontend/hooks/use-extraction.ts
git commit -m "feat: SSE hook with reconnection + extraction TanStack Query mutations"
```

---

### Task 5: Frontend — Graph mutation hooks

**Files:**
- Create: `frontend/hooks/use-graph-mutations.ts`

- [ ] **Step 1: Create the graph mutations file**

```typescript
"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api/client"

export function useRenameEntity() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ entityId, name, canonicalName, description }: {
      entityId: string
      name?: string
      canonicalName?: string
      description?: string
    }) =>
      apiFetch<{ id: string; labels: string[]; updated_properties: string[] }>(
        `/graph/entity/${entityId}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            ...(name != null ? { name } : {}),
            ...(canonicalName != null ? { canonical_name: canonicalName } : {}),
            ...(description != null ? { description } : {}),
          }),
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["graph"] })
      queryClient.invalidateQueries({ queryKey: ["book-stats"] })
    },
  })
}

export function useDeleteEntity() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (entityId: string) =>
      apiFetch<{ deleted: boolean; relationships_removed: number }>(
        `/graph/entity/${entityId}`,
        { method: "DELETE" }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["graph"] })
      queryClient.invalidateQueries({ queryKey: ["book-stats"] })
    },
  })
}

export function useMergeEntities() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ sourceId, targetId }: { sourceId: string; targetId: string }) =>
      apiFetch<{ merged_into: string; aliases_added: string[]; relationships_transferred: number }>(
        "/graph/entities/merge",
        {
          method: "POST",
          body: JSON.stringify({ source_id: sourceId, target_id: targetId }),
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["graph"] })
      queryClient.invalidateQueries({ queryKey: ["book-stats"] })
    },
  })
}

export function useDeleteRelation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (relationshipId: string) =>
      apiFetch<{ deleted: boolean }>(
        `/graph/relationship/${relationshipId}`,
        { method: "DELETE" }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["graph"] })
    },
  })
}
```

- [ ] **Step 2: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build`

- [ ] **Step 3: Commit**

```bash
git add frontend/hooks/use-graph-mutations.ts
git commit -m "feat: TanStack Query mutations for entity/relation CRUD"
```

---

### Task 6: Frontend — Shared UI components

**Files:**
- Create: `frontend/components/ui/error-state.tsx`
- Create: `frontend/components/ui/confidence-bar.tsx`
- Create: `frontend/components/ui/sse-indicator.tsx`
- Create: `frontend/components/pipeline/step-indicator.tsx`

- [ ] **Step 1: Create ErrorState**

Create `frontend/components/ui/error-state.tsx`:

```typescript
import { AlertTriangle } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"

interface ErrorStateProps {
  title: string
  message?: string
  error?: Error | null
  onRetry?: () => void
}

export function ErrorState({ title, message, error, onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
      <AlertTriangle className="h-12 w-12 text-destructive mb-4" />
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      {message && (
        <p className="mt-2 text-sm text-muted-foreground max-w-md">{message}</p>
      )}
      {onRetry && (
        <Button variant="outline" className="mt-6" onClick={onRetry}>
          Retry
        </Button>
      )}
      {error?.message && (
        <Collapsible className="mt-4 w-full max-w-md">
          <CollapsibleTrigger className="text-xs text-muted-foreground hover:underline">
            Technical details
          </CollapsibleTrigger>
          <CollapsibleContent>
            <pre className="mt-2 p-3 bg-muted rounded text-xs text-left overflow-auto max-h-40">
              {error.message}
            </pre>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Create ConfidenceBar**

Create `frontend/components/ui/confidence-bar.tsx`:

```typescript
import { cn } from "@/lib/utils"

interface ConfidenceBarProps {
  value: number
  size?: "sm" | "md"
}

function getColor(value: number): string {
  if (value < 0.3) return "bg-red-500"
  if (value < 0.7) return "bg-amber-500"
  return "bg-emerald-500"
}

export function ConfidenceBar({ value, size = "sm" }: ConfidenceBarProps) {
  const clamped = Math.max(0, Math.min(1, value))
  return (
    <div
      className={cn(
        "w-full rounded-full bg-muted",
        size === "sm" ? "h-1.5" : "h-2.5"
      )}
      title={`${Math.round(clamped * 100)}%`}
    >
      <div
        className={cn("h-full rounded-full transition-all", getColor(clamped))}
        style={{ width: `${clamped * 100}%` }}
      />
    </div>
  )
}
```

- [ ] **Step 3: Create SSEIndicator**

Create `frontend/components/ui/sse-indicator.tsx`:

```typescript
"use client"

import { cn } from "@/lib/utils"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { SSEStatus } from "@/hooks/use-extraction"

const STATUS_MAP: Record<SSEStatus, { color: string; label: string }> = {
  connecting: { color: "bg-amber-500 animate-pulse", label: "Connecting..." },
  connected: { color: "bg-emerald-500", label: "Connected" },
  reconnecting: { color: "bg-amber-500 animate-pulse", label: "Reconnecting..." },
  disconnected: { color: "bg-red-500", label: "Disconnected" },
}

export function SSEIndicator({ status }: { status: SSEStatus }) {
  const config = STATUS_MAP[status]
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={cn("inline-block h-2.5 w-2.5 rounded-full", config.color)}
            aria-label={config.label}
          />
        </TooltipTrigger>
        <TooltipContent side="top">
          <p className="text-xs">{config.label}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
```

- [ ] **Step 4: Create StepIndicator**

Create `frontend/components/pipeline/step-indicator.tsx`:

```typescript
"use client"

import { Check } from "lucide-react"
import { cn } from "@/lib/utils"

export type StepStatus = "completed" | "active" | "upcoming"

export interface Step {
  label: string
  status: StepStatus
}

interface StepIndicatorProps {
  steps: Step[]
  onStepClick: (index: number) => void
}

export function StepIndicator({ steps, onStepClick }: StepIndicatorProps) {
  return (
    <nav aria-label="Pipeline progress" className="flex items-center gap-0 w-full">
      {steps.map((step, i) => (
        <div key={step.label} className="flex items-center flex-1 last:flex-none">
          {/* Step circle + label */}
          <button
            type="button"
            disabled={step.status === "upcoming"}
            onClick={() => step.status !== "upcoming" && onStepClick(i)}
            className={cn(
              "flex items-center gap-2 text-sm font-medium transition-colors",
              step.status === "completed" && "text-emerald-500 hover:text-emerald-400 cursor-pointer",
              step.status === "active" && "text-foreground cursor-default",
              step.status === "upcoming" && "text-muted-foreground/50 cursor-not-allowed",
            )}
          >
            <span
              className={cn(
                "flex items-center justify-center h-7 w-7 rounded-full border-2 text-xs font-bold shrink-0",
                step.status === "completed" && "border-emerald-500 bg-emerald-500/10",
                step.status === "active" && "border-primary bg-primary/10 animate-pulse",
                step.status === "upcoming" && "border-muted-foreground/30",
              )}
            >
              {step.status === "completed" ? (
                <Check className="h-3.5 w-3.5" />
              ) : (
                i + 1
              )}
            </span>
            <span className="hidden sm:inline">{step.label}</span>
          </button>

          {/* Connector line */}
          {i < steps.length - 1 && (
            <div
              className={cn(
                "flex-1 h-px mx-3",
                step.status === "completed" ? "bg-emerald-500" : "bg-muted-foreground/20 border-dashed border-t",
              )}
            />
          )}
        </div>
      ))}
    </nav>
  )
}
```

- [ ] **Step 5: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build`

- [ ] **Step 6: Commit**

```bash
git add frontend/components/ui/error-state.tsx frontend/components/ui/confidence-bar.tsx frontend/components/ui/sse-indicator.tsx frontend/components/pipeline/step-indicator.tsx
git commit -m "feat: shared UI components — ErrorState, ConfidenceBar, SSEIndicator, StepIndicator"
```

---

### Task 7: Frontend — Pipeline layout & page container

**Files:**
- Create: `frontend/components/pipeline/pipeline-layout.tsx`
- Modify: `frontend/app/projects/[slug]/books/[bookId]/extraction/page.tsx`

- [ ] **Step 1: Create PipelineLayout**

Create `frontend/components/pipeline/pipeline-layout.tsx`:

```typescript
"use client"

import { AnimatePresence, motion } from "motion/react"
import { StepIndicator, type Step, type StepStatus } from "./step-indicator"

const STEP_NAMES = ["Upload", "Configure", "Extract", "Review", "Explore"] as const
export type PipelineStep = (typeof STEP_NAMES)[number]

const STEP_KEYS = ["upload", "configure", "extract", "review", "explore"] as const
export type PipelineStepKey = (typeof STEP_KEYS)[number]

interface PipelineLayoutProps {
  currentStep: PipelineStepKey
  completedSteps: Set<PipelineStepKey>
  onStepClick: (step: PipelineStepKey) => void
  children: React.ReactNode
}

export function PipelineLayout({
  currentStep,
  completedSteps,
  onStepClick,
  children,
}: PipelineLayoutProps) {
  const steps: Step[] = STEP_KEYS.map((key, i) => ({
    label: STEP_NAMES[i],
    status: (
      completedSteps.has(key) ? "completed" :
      key === currentStep ? "active" :
      "upcoming"
    ) as StepStatus,
  }))

  return (
    <div className="flex flex-col gap-8">
      <StepIndicator
        steps={steps}
        onStepClick={(i) => {
          const key = STEP_KEYS[i]
          if (completedSteps.has(key) || key === currentStep) {
            onStepClick(key)
          }
        }}
      />
      <AnimatePresence mode="wait">
        <motion.div
          key={currentStep}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2 }}
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
```

- [ ] **Step 2: Rewrite the extraction page as pipeline container**

Replace `frontend/app/projects/[slug]/books/[bookId]/extraction/page.tsx`:

```typescript
"use client"

import { use, useMemo, useCallback } from "react"
import { useQueryState, parseAsStringEnum } from "nuqs"
import { PipelineLayout, type PipelineStepKey } from "@/components/pipeline/pipeline-layout"
import { useBookDetail } from "@/hooks/use-books"
import { UploadStep } from "@/components/extraction/steps/upload-step"
import { ConfigureStep } from "@/components/extraction/steps/configure-step"
import { ExtractStep } from "@/components/extraction/steps/extract-step"
import { ReviewStep } from "@/components/extraction/steps/review-step"
import { ExploreStep } from "@/components/extraction/steps/explore-step"

const STEP_ENUM = parseAsStringEnum<PipelineStepKey>([
  "upload", "configure", "extract", "review", "explore",
]).withDefault("upload")

export default function ExtractionPipelinePage({
  params,
}: {
  params: Promise<{ slug: string; bookId: string }>
}) {
  const { slug, bookId } = use(params)
  const [step, setStep] = useQueryState("step", STEP_ENUM)
  const { data: bookDetail } = useBookDetail(bookId)

  const completedSteps = useMemo(() => {
    const completed = new Set<PipelineStepKey>()
    if (!bookDetail) return completed

    const status = bookDetail.book.status
    completed.add("upload") // always completed if we have a bookId

    if (["extracting", "extracted", "embedded", "partial", "error", "error_quota"].includes(status)) {
      completed.add("configure")
    }
    if (["extracted", "embedded"].includes(status)) {
      completed.add("extract")
      completed.add("review")
    }

    return completed
  }, [bookDetail])

  const handleStepClick = useCallback(
    (newStep: PipelineStepKey) => setStep(newStep),
    [setStep],
  )

  const goToStep = useCallback(
    (s: PipelineStepKey) => setStep(s),
    [setStep],
  )

  return (
    <div className="container max-w-6xl py-8">
      <PipelineLayout
        currentStep={step}
        completedSteps={completedSteps}
        onStepClick={handleStepClick}
      >
        {step === "upload" && (
          <UploadStep
            projectSlug={slug}
            bookId={bookId}
            onContinue={() => goToStep("configure")}
          />
        )}
        {step === "configure" && (
          <ConfigureStep
            bookId={bookId}
            onStart={() => goToStep("extract")}
          />
        )}
        {step === "extract" && (
          <ExtractStep
            bookId={bookId}
            onComplete={() => goToStep("review")}
          />
        )}
        {step === "review" && (
          <ReviewStep
            bookId={bookId}
            onContinue={() => goToStep("explore")}
          />
        )}
        {step === "explore" && (
          <ExploreStep
            projectSlug={slug}
            bookId={bookId}
          />
        )}
      </PipelineLayout>
    </div>
  )
}
```

- [ ] **Step 3: Create placeholder step components**

Each step component is created as a minimal placeholder. They will be implemented in subsequent tasks.

Create `frontend/components/extraction/steps/upload-step.tsx`:
```typescript
export function UploadStep({ projectSlug, bookId, onContinue }: { projectSlug: string; bookId: string; onContinue: () => void }) {
  return <div className="text-muted-foreground">Upload step — coming soon</div>
}
```

Create `frontend/components/extraction/steps/configure-step.tsx`:
```typescript
export function ConfigureStep({ bookId, onStart }: { bookId: string; onStart: () => void }) {
  return <div className="text-muted-foreground">Configure step — coming soon</div>
}
```

Create `frontend/components/extraction/steps/extract-step.tsx`:
```typescript
export function ExtractStep({ bookId, onComplete }: { bookId: string; onComplete: () => void }) {
  return <div className="text-muted-foreground">Extract step — coming soon</div>
}
```

Create `frontend/components/extraction/steps/review-step.tsx`:
```typescript
export function ReviewStep({ bookId, onContinue }: { bookId: string; onContinue: () => void }) {
  return <div className="text-muted-foreground">Review step — coming soon</div>
}
```

Create `frontend/components/extraction/steps/explore-step.tsx`:
```typescript
export function ExploreStep({ projectSlug, bookId }: { projectSlug: string; bookId: string }) {
  return <div className="text-muted-foreground">Explore step — coming soon</div>
}
```

- [ ] **Step 4: Delete old dashboard file**

Run: `rm frontend/app/projects/[slug]/books/[bookId]/extraction/dashboard.tsx`

- [ ] **Step 5: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build`
Note: May need to update imports in other files that referenced the old dashboard. Fix any import errors.

- [ ] **Step 6: Commit**

```bash
git add -A frontend/components/pipeline/ frontend/components/extraction/steps/ frontend/app/projects/
git commit -m "feat: pipeline layout + page container with URL-persisted steps (placeholders)"
```

---

### Task 8: Frontend — Upload step

**Files:**
- Modify: `frontend/components/extraction/steps/upload-step.tsx`

- [ ] **Step 1: Implement the upload step**

Replace `frontend/components/extraction/steps/upload-step.tsx`:

```typescript
"use client"

import { useCallback, useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Upload, BookOpen, ArrowRight, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { apiFetch } from "@/lib/api/client"
import { useBooks } from "@/hooks/use-books"
import { EmptyState } from "@/components/shared/empty-state"
import { ErrorState } from "@/components/ui/error-state"
import type { IngestionResult } from "@/lib/api/types"

interface UploadStepProps {
  projectSlug: string
  bookId: string
  onContinue: () => void
}

export function UploadStep({ projectSlug, bookId, onContinue }: UploadStepProps) {
  const queryClient = useQueryClient()
  const { data: books, isLoading, error } = useBooks(projectSlug)
  const [dragOver, setDragOver] = useState(false)

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append("file", file)
      form.append("book_num", String((books?.length ?? 0) + 1))
      return apiFetch<IngestionResult>(`/projects/${projectSlug}/books`, {
        method: "POST",
        body: form,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["books", projectSlug] })
    },
  })

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      const file = e.dataTransfer.files[0]
      if (file) uploadMutation.mutate(file)
    },
    [uploadMutation],
  )

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) uploadMutation.mutate(file)
    },
    [uploadMutation],
  )

  if (error) {
    return <ErrorState title="Failed to load books" error={error as Error} />
  }

  return (
    <div className="space-y-6">
      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`
          relative flex flex-col items-center justify-center gap-4 p-12
          border-2 border-dashed rounded-xl transition-colors cursor-pointer
          ${dragOver ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:border-muted-foreground/50"}
        `}
        onClick={() => document.getElementById("file-input")?.click()}
      >
        {uploadMutation.isPending ? (
          <>
            <Loader2 className="h-10 w-10 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Uploading & parsing...</p>
          </>
        ) : (
          <>
            <Upload className="h-10 w-10 text-muted-foreground" />
            <div className="text-center">
              <p className="text-sm font-medium">Drop your epub, pdf, or txt file here</p>
              <p className="text-xs text-muted-foreground mt-1">or click to browse</p>
            </div>
          </>
        )}
        <input
          id="file-input"
          type="file"
          accept=".epub,.pdf,.txt"
          className="hidden"
          onChange={handleFileInput}
        />
      </div>

      {/* Upload success */}
      {uploadMutation.isSuccess && uploadMutation.data && (
        <Card className="border-emerald-500/50">
          <CardContent className="flex items-center justify-between p-4">
            <div className="flex items-center gap-3">
              <BookOpen className="h-5 w-5 text-emerald-500" />
              <div>
                <p className="font-medium">{uploadMutation.data.title}</p>
                <p className="text-xs text-muted-foreground">
                  {uploadMutation.data.chapters_found} chapters &middot; {uploadMutation.data.chunks_created} chunks
                </p>
              </div>
            </div>
            <Button onClick={onContinue} size="sm">
              Configure <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
            </Button>
          </CardContent>
        </Card>
      )}

      {uploadMutation.isError && (
        <ErrorState
          title="Upload failed"
          message={(uploadMutation.error as Error).message}
          onRetry={() => uploadMutation.reset()}
        />
      )}

      {/* Existing books */}
      {!isLoading && books && books.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-3">Books in this project</h3>
          <div className="grid gap-3">
            {books.map((book) => (
              <Card
                key={book.id ?? book.book_id}
                className="cursor-pointer hover:bg-accent/50 transition-colors"
                onClick={onContinue}
              >
                <CardContent className="flex items-center justify-between p-3">
                  <div className="flex items-center gap-3">
                    <BookOpen className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">
                      {book.original_filename ?? "Book"}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground">{book.status}</span>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build`

- [ ] **Step 3: Commit**

```bash
git add frontend/components/extraction/steps/upload-step.tsx
git commit -m "feat: Upload step — drag & drop, file upload, success card"
```

---

### Task 9: Frontend — Configure step

**Files:**
- Modify: `frontend/components/extraction/steps/configure-step.tsx`

- [ ] **Step 1: Implement the configure step**

Replace `frontend/components/extraction/steps/configure-step.tsx`:

```typescript
"use client"

import { useState } from "react"
import { Swords, Wand2, Rocket, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Checkbox } from "@/components/ui/checkbox"
import { useBookDetail } from "@/hooks/use-books"
import { useTriggerExtraction } from "@/hooks/use-extraction"
import { ErrorState } from "@/components/ui/error-state"
import { cn } from "@/lib/utils"

const GENRES = [
  { key: "litrpg", label: "LitRPG", icon: Swords },
  { key: "fantasy", label: "Fantasy", icon: Wand2 },
  { key: "sci-fi", label: "Sci-Fi", icon: Rocket },
] as const

const LANGUAGES = [
  { key: "fr", label: "FR" },
  { key: "en", label: "EN" },
] as const

const PROVIDERS = [
  { key: "gemini:gemini-2.5-flash", label: "Gemini 2.5 Flash", cost: "free" },
  { key: "openrouter:deepseek/deepseek-chat-v3-0324", label: "DeepSeek V3.2", cost: "$0.26/M" },
  { key: "local:qwen3:32b", label: "Ollama (qwen3:32b)", cost: "local" },
] as const

interface ConfigureStepProps {
  bookId: string
  onStart: () => void
}

export function ConfigureStep({ bookId, onStart }: ConfigureStepProps) {
  const { data: bookDetail, isLoading, error } = useBookDetail(bookId)
  const triggerMutation = useTriggerExtraction()

  const [genre, setGenre] = useState("litrpg")
  const [language, setLanguage] = useState("fr")
  const [provider, setProvider] = useState(PROVIDERS[0].key)
  const [selectedChapters, setSelectedChapters] = useState<number[]>([])
  const [showAdvanced, setShowAdvanced] = useState(false)

  if (error) return <ErrorState title="Failed to load book" error={error as Error} />

  const chapters = bookDetail?.chapters ?? []

  const handleStart = () => {
    triggerMutation.mutate(
      {
        bookId,
        genre,
        language,
        provider,
        chapters: selectedChapters.length > 0 ? selectedChapters : undefined,
      },
      { onSuccess: onStart },
    )
  }

  const toggleChapter = (num: number) => {
    setSelectedChapters((prev) =>
      prev.includes(num) ? prev.filter((n) => n !== num) : [...prev, num],
    )
  }

  return (
    <div className="space-y-8">
      {/* Book info */}
      {bookDetail && (
        <div className="flex items-center gap-4 p-4 rounded-lg bg-muted/50">
          <div>
            <p className="font-semibold">{bookDetail.book.title}</p>
            <p className="text-xs text-muted-foreground">
              {bookDetail.book.total_chapters} chapters
              {bookDetail.book.author ? ` \u00b7 ${bookDetail.book.author}` : ""}
            </p>
          </div>
        </div>
      )}

      {/* Genre */}
      <div>
        <label className="text-sm font-medium mb-3 block">Genre</label>
        <div className="grid grid-cols-3 gap-3">
          {GENRES.map((g) => (
            <Card
              key={g.key}
              className={cn(
                "cursor-pointer transition-all hover:bg-accent/50",
                genre === g.key && "border-primary ring-1 ring-primary",
              )}
              onClick={() => setGenre(g.key)}
            >
              <CardContent className="flex flex-col items-center gap-2 p-4">
                <g.icon className="h-6 w-6" />
                <span className="text-sm font-medium">{g.label}</span>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Language */}
      <div>
        <label className="text-sm font-medium mb-3 block">Source language</label>
        <div className="flex gap-1 p-1 bg-muted rounded-lg w-fit">
          {LANGUAGES.map((l) => (
            <button
              key={l.key}
              onClick={() => setLanguage(l.key)}
              className={cn(
                "px-4 py-1.5 text-sm font-medium rounded-md transition-colors",
                language === l.key
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>

      {/* Provider */}
      <div>
        <label className="text-sm font-medium mb-3 block">LLM Provider</label>
        <Select value={provider} onValueChange={setProvider}>
          <SelectTrigger className="w-full max-w-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PROVIDERS.map((p) => (
              <SelectItem key={p.key} value={p.key}>
                <span>{p.label}</span>
                <span className="ml-2 text-xs text-muted-foreground">({p.cost})</span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Advanced: chapter selection */}
      <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
        <CollapsibleTrigger className="text-sm text-muted-foreground hover:underline">
          {showAdvanced ? "Hide" : "Show"} advanced options
        </CollapsibleTrigger>
        <CollapsibleContent className="mt-3">
          <p className="text-xs text-muted-foreground mb-2">
            Select specific chapters to extract (leave empty for all):
          </p>
          <div className="grid grid-cols-6 sm:grid-cols-8 md:grid-cols-10 gap-2 max-h-48 overflow-auto">
            {chapters.map((ch) => (
              <label
                key={ch.number}
                className="flex items-center gap-1.5 text-xs cursor-pointer"
              >
                <Checkbox
                  checked={selectedChapters.includes(ch.number)}
                  onCheckedChange={() => toggleChapter(ch.number)}
                />
                {ch.number}
              </label>
            ))}
          </div>
        </CollapsibleContent>
      </Collapsible>

      {/* CTA */}
      <Button
        size="lg"
        className="w-full"
        onClick={handleStart}
        disabled={triggerMutation.isPending || isLoading}
      >
        {triggerMutation.isPending ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Starting...
          </>
        ) : (
          "Start extraction"
        )}
      </Button>

      {triggerMutation.isError && (
        <ErrorState
          title="Failed to start extraction"
          error={triggerMutation.error as Error}
          onRetry={() => triggerMutation.reset()}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build`

- [ ] **Step 3: Commit**

```bash
git add frontend/components/extraction/steps/configure-step.tsx
git commit -m "feat: Configure step — genre cards, language toggle, provider select, chapter picker"
```

---

### Task 10: Frontend — Extract step (real-time progress)

**Files:**
- Modify: `frontend/components/extraction/steps/extract-step.tsx`
- Create: `frontend/components/extraction/chapter-progress-list.tsx`
- Create: `frontend/components/extraction/extraction-live-stats.tsx`

- [ ] **Step 1: Create ChapterProgressList**

Create `frontend/components/extraction/chapter-progress-list.tsx`:

```typescript
"use client"

import { Check, X, Clock, Loader2, RotateCcw, ChevronDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import type { ChapterProgress } from "@/hooks/use-extraction"
import type { ChapterInfo } from "@/lib/api/types"
import { cn } from "@/lib/utils"

interface ChapterProgressListProps {
  chapters: ChapterInfo[]
  progress: Map<number, ChapterProgress>
  onRetry: (chapter: number) => void
}

const STATUS_ICON = {
  pending: Clock,
  extracting: Loader2,
  done: Check,
  failed: X,
}

export function ChapterProgressList({ chapters, progress, onRetry }: ChapterProgressListProps) {
  return (
    <div className="space-y-1">
      {chapters.map((ch) => {
        const p = progress.get(ch.number)
        const status = p?.status ?? "pending"
        const Icon = STATUS_ICON[status]

        return (
          <Collapsible key={ch.number}>
            <div
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                status === "extracting" && "bg-primary/5",
                status === "failed" && "bg-destructive/5",
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 shrink-0",
                  status === "done" && "text-emerald-500",
                  status === "failed" && "text-destructive",
                  status === "extracting" && "text-primary animate-spin",
                  status === "pending" && "text-muted-foreground",
                )}
              />
              <span className="flex-1 truncate">
                <span className="font-mono text-xs text-muted-foreground mr-2">
                  {String(ch.number).padStart(2, "0")}
                </span>
                {ch.title || `Chapter ${ch.number}`}
              </span>

              {p?.entities != null && p.entities > 0 && (
                <Badge variant="secondary" className="text-xs">
                  {p.entities}
                </Badge>
              )}

              {status === "failed" && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={() => onRetry(ch.number)}
                >
                  <RotateCcw className="h-3 w-3" />
                </Button>
              )}

              {status === "done" && (
                <CollapsibleTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-6 w-6">
                    <ChevronDown className="h-3 w-3" />
                  </Button>
                </CollapsibleTrigger>
              )}
            </div>

            <CollapsibleContent>
              <div className="ml-10 px-3 py-2 text-xs text-muted-foreground">
                {p?.entities ?? 0} entities extracted
                {p?.duration_ms != null && ` \u00b7 ${(p.duration_ms / 1000).toFixed(1)}s`}
                {p?.error && (
                  <span className="text-destructive ml-2">{p.error}</span>
                )}
              </div>
            </CollapsibleContent>
          </Collapsible>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 2: Create ExtractionLiveStats**

Create `frontend/components/extraction/extraction-live-stats.tsx`:

```typescript
"use client"

import { motion, AnimatePresence } from "motion/react"
import { Progress } from "@/components/ui/progress"
import { SSEIndicator } from "@/components/ui/sse-indicator"
import type { SSEStatus } from "@/hooks/use-extraction"

interface ExtractionLiveStatsProps {
  totalEntities: number
  chaptersDone: number
  chaptersTotal: number
  sseStatus: SSEStatus
  costUsd?: number
}

export function ExtractionLiveStats({
  totalEntities,
  chaptersDone,
  chaptersTotal,
  sseStatus,
  costUsd,
}: ExtractionLiveStatsProps) {
  const pct = chaptersTotal > 0 ? (chaptersDone / chaptersTotal) * 100 : 0

  return (
    <div className="space-y-6">
      {/* Total entities */}
      <div className="text-center">
        <AnimatePresence mode="popLayout">
          <motion.p
            key={totalEntities}
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-4xl font-bold tabular-nums"
          >
            {totalEntities}
          </motion.p>
        </AnimatePresence>
        <p className="text-xs text-muted-foreground mt-1">entities extracted</p>
      </div>

      {/* Progress bar */}
      <div>
        <div className="flex justify-between text-xs text-muted-foreground mb-1.5">
          <span>Progress</span>
          <span className="tabular-nums">{chaptersDone}/{chaptersTotal}</span>
        </div>
        <Progress value={pct} className="h-2" />
      </div>

      {/* Cost */}
      {costUsd != null && costUsd > 0 && (
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Cost</span>
          <span className="font-mono tabular-nums">${costUsd.toFixed(3)}</span>
        </div>
      )}

      {/* SSE status */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">Connection</span>
        <SSEIndicator status={sseStatus} />
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Implement ExtractStep**

Replace `frontend/components/extraction/steps/extract-step.tsx`:

```typescript
"use client"

import { useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useBookDetail } from "@/hooks/use-books"
import { useExtractionSSE, useRetryChapter } from "@/hooks/use-extraction"
import { ChapterProgressList } from "@/components/extraction/chapter-progress-list"
import { ExtractionLiveStats } from "@/components/extraction/extraction-live-stats"
import { ErrorState } from "@/components/ui/error-state"

interface ExtractStepProps {
  bookId: string
  onComplete: () => void
}

export function ExtractStep({ bookId, onComplete }: ExtractStepProps) {
  const { data: bookDetail } = useBookDetail(bookId)
  const sse = useExtractionSSE(bookId)
  const retryMutation = useRetryChapter()

  // Auto-connect on mount
  useEffect(() => {
    sse.connect()
    return () => sse.disconnect()
  }, [bookId])

  // Auto-advance when done
  useEffect(() => {
    if (sse.isDone) {
      const timer = setTimeout(onComplete, 2000)
      return () => clearTimeout(timer)
    }
  }, [sse.isDone, onComplete])

  const chapters = bookDetail?.chapters ?? []

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Left: chapter list */}
      <div className="lg:col-span-2">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Chapters</CardTitle>
          </CardHeader>
          <CardContent className="max-h-[60vh] overflow-auto">
            <ChapterProgressList
              chapters={chapters}
              progress={sse.chapters}
              onRetry={(ch) => retryMutation.mutate({ bookId, chapter: ch })}
            />
          </CardContent>
        </Card>
      </div>

      {/* Right: live stats */}
      <div>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Progress</CardTitle>
          </CardHeader>
          <CardContent>
            <ExtractionLiveStats
              totalEntities={sse.totalEntities}
              chaptersDone={sse.chaptersDone}
              chaptersTotal={sse.chaptersTotal}
              sseStatus={sse.sseStatus}
            />
          </CardContent>
        </Card>

        {sse.error && (
          <ErrorState
            title="Extraction error"
            message={sse.error}
            onRetry={() => sse.connect()}
          />
        )}

        {sse.isDone && (
          <Card className="mt-4 border-emerald-500/50">
            <CardContent className="p-4 text-center">
              <p className="text-sm font-medium text-emerald-500">Extraction complete</p>
              <Button className="mt-3" size="sm" onClick={onComplete}>
                Review results
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build`

- [ ] **Step 5: Commit**

```bash
git add frontend/components/extraction/steps/extract-step.tsx frontend/components/extraction/chapter-progress-list.tsx frontend/components/extraction/extraction-live-stats.tsx
git commit -m "feat: Extract step — real-time SSE progress, chapter list, live stats"
```

---

### Task 11: Frontend — Review step with entity table

**Files:**
- Modify: `frontend/components/extraction/steps/review-step.tsx`
- Create: `frontend/components/extraction/review/entity-review-table.tsx`
- Create: `frontend/components/extraction/review/relation-review-table.tsx`
- Create: `frontend/components/extraction/review/problems-panel.tsx`

- [ ] **Step 1: Create EntityReviewTable**

Create `frontend/components/extraction/review/entity-review-table.tsx`:

```typescript
"use client"

import { useState, useMemo } from "react"
import { MoreHorizontal, Pencil, Trash2, Merge, Check, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Checkbox } from "@/components/ui/checkbox"
import { Badge } from "@/components/ui/badge"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { ConfidenceBar } from "@/components/ui/confidence-bar"
import { useRenameEntity, useDeleteEntity, useMergeEntities } from "@/hooks/use-graph-mutations"
import { ENTITY_COLORS } from "@/lib/constants"
import type { GraphNode } from "@/lib/api/types"
import { cn } from "@/lib/utils"

interface EntityReviewTableProps {
  entities: GraphNode[]
  bookId: string
}

export function EntityReviewTable({ entities, bookId }: EntityReviewTableProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState("")
  const [mergeDialogOpen, setMergeDialogOpen] = useState(false)
  const [filterType, setFilterType] = useState<string | null>(null)
  const [search, setSearch] = useState("")

  const renameMutation = useRenameEntity()
  const deleteMutation = useDeleteEntity()
  const mergeMutation = useMergeEntities()

  const filtered = useMemo(() => {
    let result = entities
    if (filterType) {
      result = result.filter((e) => e.labels.includes(filterType))
    }
    if (search) {
      const q = search.toLowerCase()
      result = result.filter((e) => e.name.toLowerCase().includes(q))
    }
    return result
  }, [entities, filterType, search])

  const entityTypes = useMemo(
    () => [...new Set(entities.flatMap((e) => e.labels))].sort(),
    [entities],
  )

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const startRename = (entity: GraphNode) => {
    setEditingId(entity.id)
    setEditName(entity.name)
  }

  const confirmRename = () => {
    if (!editingId || !editName.trim()) return
    renameMutation.mutate(
      { entityId: editingId, name: editName.trim(), canonicalName: editName.trim().toLowerCase() },
      { onSuccess: () => setEditingId(null) },
    )
  }

  const handleDelete = (id: string) => {
    if (confirm("Delete this entity and all its relationships?")) {
      deleteMutation.mutate(id)
    }
  }

  const handleMerge = () => {
    const ids = Array.from(selected)
    if (ids.length !== 2) return
    mergeMutation.mutate(
      { sourceId: ids[0], targetId: ids[1] },
      {
        onSuccess: () => {
          setSelected(new Set())
          setMergeDialogOpen(false)
        },
      },
    )
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-3">
        <Input
          placeholder="Search entities..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs h-8 text-sm"
        />
        <div className="flex gap-1 flex-wrap">
          <Badge
            variant={filterType === null ? "default" : "outline"}
            className="cursor-pointer text-xs"
            onClick={() => setFilterType(null)}
          >
            All
          </Badge>
          {entityTypes.map((t) => (
            <Badge
              key={t}
              variant={filterType === t ? "default" : "outline"}
              className="cursor-pointer text-xs"
              onClick={() => setFilterType(filterType === t ? null : t)}
            >
              {t}
            </Badge>
          ))}
        </div>
      </div>

      {/* Bulk actions */}
      {selected.size > 0 && (
        <div className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">{selected.size} selected</span>
          {selected.size === 2 && (
            <Button variant="outline" size="sm" onClick={() => setMergeDialogOpen(true)}>
              <Merge className="mr-1.5 h-3 w-3" /> Merge
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            className="text-destructive"
            onClick={() => {
              if (confirm(`Delete ${selected.size} entities?`)) {
                selected.forEach((id) => deleteMutation.mutate(id))
                setSelected(new Set())
              }
            }}
          >
            <Trash2 className="mr-1.5 h-3 w-3" /> Delete
          </Button>
        </div>
      )}

      {/* Table */}
      <div className="border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="w-8 p-2" />
              <th className="text-left p-2 font-medium">Name</th>
              <th className="text-left p-2 font-medium">Type</th>
              <th className="text-left p-2 font-medium w-24">Confidence</th>
              <th className="w-10 p-2" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((entity) => (
              <tr key={entity.id} className="border-b last:border-0 hover:bg-muted/30">
                <td className="p-2">
                  <Checkbox
                    checked={selected.has(entity.id)}
                    onCheckedChange={() => toggleSelect(entity.id)}
                  />
                </td>
                <td className="p-2">
                  {editingId === entity.id ? (
                    <div className="flex items-center gap-1">
                      <Input
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        className="h-7 text-sm"
                        autoFocus
                        onKeyDown={(e) => e.key === "Enter" && confirmRename()}
                      />
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={confirmRename}>
                        <Check className="h-3 w-3" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setEditingId(null)}>
                        <X className="h-3 w-3" />
                      </Button>
                    </div>
                  ) : (
                    <span className="font-medium">{entity.name}</span>
                  )}
                </td>
                <td className="p-2">
                  <Badge
                    variant="outline"
                    className="text-xs"
                    style={{
                      borderColor: ENTITY_COLORS[entity.labels[0]]
                        ? `var(--color-${ENTITY_COLORS[entity.labels[0]]})`
                        : undefined,
                    }}
                  >
                    {entity.labels[0]}
                  </Badge>
                </td>
                <td className="p-2">
                  <ConfidenceBar value={entity.score ?? 1.0} />
                </td>
                <td className="p-2">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-7 w-7">
                        <MoreHorizontal className="h-3.5 w-3.5" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => startRename(entity)}>
                        <Pencil className="mr-2 h-3.5 w-3.5" /> Rename
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => handleDelete(entity.id)}
                      >
                        <Trash2 className="mr-2 h-3.5 w-3.5" /> Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Merge dialog */}
      <Dialog open={mergeDialogOpen} onOpenChange={setMergeDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Merge entities</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            The first selected entity will be merged into the second. All relationships
            will be transferred and the first entity will be deleted.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setMergeDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleMerge} disabled={mergeMutation.isPending}>
              Merge
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
```

- [ ] **Step 2: Create RelationReviewTable**

Create `frontend/components/extraction/review/relation-review-table.tsx`:

```typescript
"use client"

import { Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { useDeleteRelation } from "@/hooks/use-graph-mutations"
import type { GraphEdge, GraphNode } from "@/lib/api/types"

interface RelationReviewTableProps {
  edges: GraphEdge[]
  nodes: GraphNode[]
}

export function RelationReviewTable({ edges, nodes }: RelationReviewTableProps) {
  const deleteMutation = useDeleteRelation()

  const nameMap = new Map(nodes.map((n) => [n.id, n.name]))

  const handleDelete = (id: string) => {
    if (confirm("Delete this relationship?")) {
      deleteMutation.mutate(id)
    }
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="text-left p-2 font-medium">Source</th>
            <th className="text-left p-2 font-medium">Type</th>
            <th className="text-left p-2 font-medium">Target</th>
            <th className="w-10 p-2" />
          </tr>
        </thead>
        <tbody>
          {edges.map((edge) => (
            <tr key={edge.id} className="border-b last:border-0 hover:bg-muted/30">
              <td className="p-2 font-medium">{nameMap.get(edge.source) ?? edge.source}</td>
              <td className="p-2">
                <Badge variant="outline" className="text-xs font-mono">
                  {edge.type}
                </Badge>
              </td>
              <td className="p-2 font-medium">{nameMap.get(edge.target) ?? edge.target}</td>
              <td className="p-2">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-destructive"
                  onClick={() => handleDelete(edge.id)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 3: Create ProblemsPanel**

Create `frontend/components/extraction/review/problems-panel.tsx`:

```typescript
"use client"

import { AlertTriangle, RotateCcw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { useRetryChapter, useDLQEntries } from "@/hooks/use-extraction"
import { EmptyState } from "@/components/shared/empty-state"

interface ProblemsPanelProps {
  bookId: string
}

export function ProblemsPanel({ bookId }: ProblemsPanelProps) {
  const { data: dlq } = useDLQEntries(bookId)
  const retryMutation = useRetryChapter()

  const entries = dlq?.entries ?? []

  if (entries.length === 0) {
    return (
      <EmptyState
        title="No problems found"
        description="All chapters extracted successfully."
      />
    )
  }

  return (
    <div className="space-y-4">
      {/* Failed chapters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-destructive" />
            Failed chapters ({entries.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {entries.map((entry) => (
            <Collapsible key={`${entry.book_id}-${entry.chapter}`}>
              <div className="flex items-center justify-between p-2 rounded-lg bg-muted/50">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs">Ch. {entry.chapter}</span>
                  <span className="text-xs text-destructive">{entry.error_type}</span>
                </div>
                <div className="flex items-center gap-1">
                  <CollapsibleTrigger className="text-xs text-muted-foreground hover:underline">
                    Details
                  </CollapsibleTrigger>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={() => retryMutation.mutate({ bookId, chapter: entry.chapter })}
                    disabled={retryMutation.isPending}
                  >
                    <RotateCcw className="mr-1 h-3 w-3" /> Retry
                  </Button>
                </div>
              </div>
              <CollapsibleContent>
                <pre className="mt-1 p-2 text-xs text-muted-foreground bg-muted rounded overflow-auto max-h-24">
                  {entry.error_message}
                </pre>
              </CollapsibleContent>
            </Collapsible>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
```

- [ ] **Step 4: Implement ReviewStep**

Replace `frontend/components/extraction/steps/review-step.tsx`:

```typescript
"use client"

import { useQuery } from "@tanstack/react-query"
import { ArrowRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { apiFetch } from "@/lib/api/client"
import { useBookDetail } from "@/hooks/use-books"
import { EntityReviewTable } from "@/components/extraction/review/entity-review-table"
import { RelationReviewTable } from "@/components/extraction/review/relation-review-table"
import { ProblemsPanel } from "@/components/extraction/review/problems-panel"
import { ErrorState } from "@/components/ui/error-state"
import { EmptyState } from "@/components/shared/empty-state"
import type { SubgraphData } from "@/lib/api/types"
import { Loader2, Search } from "lucide-react"

interface ReviewStepProps {
  bookId: string
  onContinue: () => void
}

export function ReviewStep({ bookId, onContinue }: ReviewStepProps) {
  const { data: bookDetail } = useBookDetail(bookId)

  const { data: subgraph, isLoading, error } = useQuery({
    queryKey: ["graph", "subgraph", bookId],
    queryFn: () => apiFetch<SubgraphData>(`/graph/subgraph/${bookId}`),
    enabled: !!bookId,
    staleTime: 60_000,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return <ErrorState title="Failed to load extraction results" error={error as Error} />
  }

  const nodes = subgraph?.nodes ?? []
  const edges = subgraph?.edges ?? []

  return (
    <div className="space-y-6">
      <Tabs defaultValue="entities">
        <TabsList>
          <TabsTrigger value="entities">
            Entities ({nodes.length})
          </TabsTrigger>
          <TabsTrigger value="relations">
            Relations ({edges.length})
          </TabsTrigger>
          <TabsTrigger value="problems">
            Problems
          </TabsTrigger>
        </TabsList>

        <TabsContent value="entities" className="mt-4">
          {nodes.length === 0 ? (
            <EmptyState
              icon={<Search className="h-8 w-8 text-muted-foreground" />}
              title="No entities found"
              description="The extraction didn't produce any entities for this book."
            />
          ) : (
            <EntityReviewTable entities={nodes} bookId={bookId} />
          )}
        </TabsContent>

        <TabsContent value="relations" className="mt-4">
          {edges.length === 0 ? (
            <EmptyState
              icon={<Search className="h-8 w-8 text-muted-foreground" />}
              title="No relations found"
            />
          ) : (
            <RelationReviewTable edges={edges} nodes={nodes} />
          )}
        </TabsContent>

        <TabsContent value="problems" className="mt-4">
          <ProblemsPanel bookId={bookId} />
        </TabsContent>
      </Tabs>

      <div className="flex justify-end">
        <Button onClick={onContinue}>
          Explore graph <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build`

- [ ] **Step 6: Commit**

```bash
git add frontend/components/extraction/steps/review-step.tsx frontend/components/extraction/review/
git commit -m "feat: Review step — entity table (rename/delete/merge), relation table, problems panel"
```

---

### Task 12: Frontend — Explore step

**Files:**
- Modify: `frontend/components/extraction/steps/explore-step.tsx`

- [ ] **Step 1: Implement the explore step**

Replace `frontend/components/extraction/steps/explore-step.tsx`:

```typescript
"use client"

import Link from "next/link"
import { ExternalLink, Download } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { useBookStats } from "@/hooks/use-books"

interface ExploreStepProps {
  projectSlug: string
  bookId: string
}

export function ExploreStep({ projectSlug, bookId }: ExploreStepProps) {
  const { data: stats } = useBookStats(bookId)

  return (
    <Card className="border-emerald-500/30">
      <CardContent className="flex flex-col items-center gap-6 py-12">
        <div className="text-center">
          <h2 className="text-2xl font-bold">Your Knowledge Graph is ready</h2>
          <p className="text-muted-foreground mt-2">
            {stats ? `${Object.values(stats).reduce((a: number, b) => a + (typeof b === "number" ? b : 0), 0)} nodes extracted` : "Extraction complete"}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button asChild size="lg">
            <Link href={`/projects/${projectSlug}/graph?book=${bookId}`}>
              Open Graph Explorer <ExternalLink className="ml-1.5 h-4 w-4" />
            </Link>
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="lg">
                <Download className="mr-1.5 h-4 w-4" /> Export
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem asChild>
                <a href={`/api/projects/${projectSlug}/export/cypher`} target="_blank" rel="noreferrer">
                  Cypher
                </a>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <a href={`/api/projects/${projectSlug}/export/jsonld`} target="_blank" rel="noreferrer">
                  JSON-LD
                </a>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <a href={`/api/projects/${projectSlug}/export/csv`} target="_blank" rel="noreferrer">
                  CSV
                </a>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardContent>
    </Card>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build`

- [ ] **Step 3: Commit**

```bash
git add frontend/components/extraction/steps/explore-step.tsx
git commit -m "feat: Explore step — graph explorer CTA + export dropdown"
```

---

### Task 13: Cleanup — delete old files

**Files:**
- Delete: `frontend/hooks/use-extraction-stream.ts`
- Delete: `frontend/stores/extraction-store.ts`
- Delete: `frontend/stores/graph-store.ts`

- [ ] **Step 1: Delete old files**

```bash
rm frontend/hooks/use-extraction-stream.ts
rm frontend/stores/extraction-store.ts
rm frontend/stores/graph-store.ts
```

- [ ] **Step 2: Find and fix broken imports**

Run: `cd /home/ringuet/WorldRAG/frontend && grep -r "use-extraction-stream\|extraction-store\|graph-store" --include="*.ts" --include="*.tsx" -l`

For each file found, update imports to use the new hooks (`use-extraction.ts`, `use-books.ts`). If a file uses `useExtractionStore`, replace with the appropriate TanStack Query hook.

- [ ] **Step 3: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: delete old extraction-store, graph-store, use-extraction-stream (replaced by TanStack Query)"
```

---

### Task 14: Full integration test

- [ ] **Step 1: Run backend tests**

Run: `cd /home/ringuet/WorldRAG && uv run pytest backend/tests/ -x --tb=short -q`
Expected: All tests pass

- [ ] **Step 2: Run frontend build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 3: Run frontend lint**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run lint`
Expected: No errors

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: extraction UI redesign — pipeline flow, TanStack Query, SSE reconnection, entity CRUD"
```
