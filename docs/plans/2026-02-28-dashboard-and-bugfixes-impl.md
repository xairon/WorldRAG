# Dashboard & Bugfixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix Characters page showing mixed entity types, fix wiki duplicate key error, and build a comprehensive extraction dashboard with progress bar, entity counts, per-chapter status, and DLQ retry UI.

**Architecture:** Backend gets a new `/graph/entities` endpoint for clean entity listing. Existing subgraph Cypher gets a label filter fix. The extraction dashboard reuses existing SSE + polling APIs (`/books/{id}`, `/graph/stats`, `/admin/dlq`) with a new rich UI.

**Tech Stack:** FastAPI + Neo4j (Cypher) backend, Next.js 16 + React 19 + Tailwind + shadcn/ui frontend.

---

### Task 1: Backend — New `/graph/entities` endpoint

**Files:**
- Modify: `backend/app/api/routes/graph.py` (after line 378)
- Modify: `frontend/lib/api/graph.ts` (add new function)
- Modify: `frontend/lib/api/types.ts` (add new type)

**Step 1: Add the endpoint to graph.py**

Add after the `get_book_subgraph` function (line 378):

```python
@router.get("/entities", dependencies=[Depends(require_auth)])
async def list_entities(
    book_id: str = Query(..., description="Book ID"),
    label: str = Query(..., description="Entity label (Character, Skill, etc.)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    driver: AsyncDriver = Depends(get_neo4j),
) -> dict:
    """List entities of a specific type for a book, with pagination."""
    if label not in ALLOWED_LABELS:
        raise HTTPException(status_code=400, detail=f"Invalid label: {label}")

    repo = Neo4jRepository(driver)

    # Count total
    count_result = await repo.execute_read(
        """
        MATCH (n)
        WHERE n.book_id = $book_id AND $label IN labels(n)
        RETURN count(n) AS total
        """,
        {"book_id": book_id, "label": label},
    )
    total = count_result[0]["total"] if count_result else 0

    # Fetch page
    results = await repo.execute_read(
        """
        MATCH (n)
        WHERE n.book_id = $book_id AND $label IN labels(n)
        RETURN elementId(n) AS id,
               labels(n) AS labels,
               n.name AS name,
               n.canonical_name AS canonical_name,
               n.description AS description
        ORDER BY n.name
        SKIP $offset LIMIT $limit
        """,
        {"book_id": book_id, "label": label, "offset": offset, "limit": limit},
    )

    return {
        "entities": [dict(r) for r in results],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
```

**Step 2: Add frontend API function**

In `frontend/lib/api/graph.ts`, add:

```typescript
export function listEntities(
  bookId: string,
  label: string,
  limit = 50,
  offset = 0,
): Promise<{ entities: GraphNode[]; total: number; limit: number; offset: number }> {
  const params = new URLSearchParams({
    book_id: bookId,
    label,
    limit: String(limit),
    offset: String(offset),
  })
  return apiFetch(`/graph/entities?${params}`)
}
```

**Step 3: Verify endpoint works**

Run: `curl -s "http://localhost:8000/api/graph/entities?book_id=b31d3c8d&label=Character&limit=10" | python -m json.tool | head -20`
Expected: JSON with `entities` array of Character nodes only, `total` count

**Step 4: Commit**

```bash
git add backend/app/api/routes/graph.py frontend/lib/api/graph.ts
git commit -m "feat: add /graph/entities endpoint for clean entity listing"
```

---

### Task 2: Fix Characters page to use new endpoint

**Files:**
- Modify: `frontend/app/(explorer)/characters/page.tsx` (lines 6, 30-31)

**Step 1: Replace getSubgraph with listEntities**

Change line 6:
```typescript
// OLD
import { listBooks, getSubgraph } from "@/lib/api"
// NEW
import { listBooks } from "@/lib/api"
import { listEntities } from "@/lib/api/graph"
```

Change lines 29-33:
```typescript
// OLD
    setLoading(true)
    getSubgraph(bookId, "Character")
      .then((data) => setCharacters(data.nodes))
      .catch(() => setCharacters([]))
      .finally(() => setLoading(false))
// NEW
    setLoading(true)
    listEntities(bookId, "Character", 200)
      .then((data) => setCharacters(data.entities))
      .catch(() => setCharacters([]))
      .finally(() => setLoading(false))
```

**Step 2: Verify in browser**

Navigate to `http://localhost:3500/characters`, select the book. Should show ONLY characters now — no events, concepts, or skills mixed in.

**Step 3: Commit**

```bash
git add frontend/app/(explorer)/characters/page.tsx
git commit -m "fix: characters page uses /graph/entities instead of subgraph"
```

---

### Task 3: Fix subgraph Cypher label filter

**Files:**
- Modify: `backend/app/api/routes/graph.py` (lines 323-363)

**Step 1: Fix the Cypher query**

The current filter `($label IN labels(n) OR $label IN labels(m))` returns both nodes even if only one matches. Fix by adding a post-filter to nodes:

Replace the entire Cypher query (lines 323-353) with:

```python
    results = await repo.execute_read(
        """
        MATCH (n)-[r]-(m)
        WHERE (n.book_id = $book_id OR m.book_id = $book_id)
          AND NOT n:Chunk AND NOT n:Book AND NOT n:Chapter
          AND NOT m:Chunk AND NOT m:Book AND NOT m:Chapter
          AND (CASE WHEN $has_label THEN ($label IN labels(n) OR $label IN labels(m)) ELSE true END)
          AND (CASE WHEN $has_chapter
               THEN (r.valid_from_chapter IS NULL OR r.valid_from_chapter <= $chapter)
                    AND (r.valid_to_chapter IS NULL OR r.valid_to_chapter >= $chapter)
               ELSE true END)
        WITH n, r, m
        LIMIT $limit
        WITH collect(DISTINCT {
            id: elementId(n),
            labels: labels(n),
            name: n.name,
            description: n.description
        }) + collect(DISTINCT {
            id: elementId(m),
            labels: labels(m),
            name: m.name,
            description: m.description
        }) AS all_nodes,
        collect(DISTINCT {
            id: elementId(r),
            type: type(r),
            source: elementId(startNode(r)),
            target: elementId(endNode(r)),
            properties: properties(r)
        }) AS edges
        // Post-filter nodes: if label specified, only keep matching ones
        UNWIND all_nodes AS node
        WITH CASE WHEN $has_label THEN
            CASE WHEN $label IN node.labels THEN node ELSE null END
          ELSE node END AS filtered_node,
          edges
        WHERE filtered_node IS NOT NULL
        RETURN collect(DISTINCT filtered_node) AS nodes, edges[0] AS edges_raw
        """,
```

Wait — actually that's getting too complex in Cypher. Simpler approach: do the filtering in Python post-processing (lines 369-378 already have dedup logic). Add label filtering there:

In the dedup section (lines 369-378), change to:

```python
    row = results[0]
    # Deduplicate nodes by id, and optionally filter by label
    seen_ids: set[str] = set()
    unique_nodes = []
    for n in row.get("nodes", []):
        nid = n.get("id")
        if nid and nid not in seen_ids:
            # If label filter active, only include nodes matching that label
            if label and label in ALLOWED_LABELS:
                node_labels = n.get("labels", [])
                if label not in node_labels:
                    continue
            seen_ids.add(nid)
            unique_nodes.append(n)
```

**Step 2: Verify**

Run: `curl -s "http://localhost:8000/api/graph/subgraph/b31d3c8d?label=Character" | python -c "import sys,json; d=json.load(sys.stdin); labels=set(); [labels.update(n['labels']) for n in d['nodes']]; print(labels)"`
Expected: Only `{'Character'}`, not mixed types.

**Step 3: Commit**

```bash
git add backend/app/api/routes/graph.py
git commit -m "fix: subgraph endpoint filters nodes by label in post-processing"
```

---

### Task 4: Fix wiki page duplicate key error

**Files:**
- Modify: `frontend/app/(explorer)/entity/[type]/[name]/page.tsx` (lines 151-161)

**Step 1: Deduplicate appearances and fix key**

Replace lines 151-161 with:

```tsx
            <div className="flex flex-wrap gap-1.5">
              {wiki.appearances
                .filter((app, i, arr) => arr.findIndex((a) => a.chapter === app.chapter) === i)
                .map((app, i) => (
                <Badge
                  key={`ch-${app.chapter}-${i}`}
                  variant="outline"
                  className="text-xs border-slate-700 text-slate-400"
                >
                  Ch. {app.chapter}
                  {app.title ? ` — ${app.title}` : ""}
                </Badge>
              ))}
            </div>
```

**Step 2: Verify**

Navigate to `http://localhost:3500/entity/Character/Jacob`. Console should show no duplicate key warnings.

**Step 3: Commit**

```bash
git add "frontend/app/(explorer)/entity/[type]/[name]/page.tsx"
git commit -m "fix: deduplicate wiki appearances and use unique React key"
```

---

### Task 5: Backend — DLQ endpoint with book_id filter

**Files:**
- Modify: `backend/app/api/routes/admin.py` (lines 57-76)

**Step 1: Add book_id filter param to DLQ list endpoint**

Change the `list_dlq` function:

```python
@router.get("/dlq", dependencies=[Depends(require_admin)])
async def list_dlq(
    book_id: str | None = Query(None, description="Filter by book ID"),
    dlq: DeadLetterQueue = Depends(get_dlq),
) -> dict:
    """List all entries in the Dead Letter Queue."""
    entries = await dlq.list_all()
    if book_id:
        entries = [e for e in entries if e.book_id == book_id]
    return {
        "count": len(entries),
        "entries": [
            {
                "book_id": e.book_id,
                "chapter": e.chapter,
                "error_type": e.error_type,
                "error_message": e.error_message,
                "timestamp": e.timestamp,
                "attempt_count": e.attempt_count,
            }
            for e in entries
        ],
    }
```

**Step 2: Add frontend API function**

In `frontend/lib/api/books.ts`, add:

```typescript
export interface DLQEntry {
  book_id: string
  chapter: number
  error_type: string
  error_message: string
  timestamp: string
  attempt_count: number
}

export function getDLQ(bookId?: string): Promise<{ count: number; entries: DLQEntry[] }> {
  const q = bookId ? `?book_id=${bookId}` : ""
  return apiFetch(`/admin/dlq${q}`)
}

export function retryDLQChapter(bookId: string, chapter: number): Promise<unknown> {
  return apiFetch(`/admin/dlq/retry/${bookId}/${chapter}`, { method: "POST" })
}

export function retryAllDLQ(): Promise<unknown> {
  return apiFetch(`/admin/dlq/retry-all`, { method: "POST" })
}
```

**Step 3: Commit**

```bash
git add backend/app/api/routes/admin.py frontend/lib/api/books.ts
git commit -m "feat: DLQ API with book_id filter + frontend API functions"
```

---

### Task 6: Frontend — Extraction Dashboard component

**Files:**
- Rewrite: `frontend/components/shared/extraction-progress.tsx`

**Step 1: Rewrite the ExtractionProgress component**

This is the main component that replaces the simple spinner. New version includes:
- Progress bar with % and chapter count
- Entity count badges by type (from polling `/graph/stats`)
- Per-chapter table with status icons
- DLQ section with retry buttons

```tsx
"use client"

import { useState, useEffect, useCallback } from "react"
import {
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  RefreshCw,
  ChevronDown,
  ChevronUp,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { LABEL_COLORS } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { ExtractionEvent } from "@/hooks/use-extraction-progress"
import type { ChapterInfo, GraphStats, DLQEntry } from "@/lib/api/types"
import { getGraphStats } from "@/lib/api/graph"
import { getBook, getDLQ, retryDLQChapter, retryAllDLQ } from "@/lib/api/books"

interface ExtractionDashboardProps {
  bookId: string
  events: ExtractionEvent[]
  progress: number
  isConnected: boolean
  isDone: boolean
  isStarted?: boolean
  totalChapters?: number
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  pending: <Clock className="h-3.5 w-3.5 text-slate-500" />,
  extracting: <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-400" />,
  extracted: <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />,
  failed: <XCircle className="h-3.5 w-3.5 text-red-400" />,
}

// Friendly labels for entity types
const ENTITY_ICONS: Record<string, string> = {
  Character: "\ud83d\udc64",
  Skill: "\u2694\ufe0f",
  Class: "\ud83d\udee1\ufe0f",
  Title: "\ud83d\udc51",
  Event: "\ud83c\udfaf",
  Location: "\ud83c\udff0",
  Item: "\ud83d\udce6",
  Creature: "\ud83d\udc32",
  Faction: "\u2694",
  Concept: "\ud83d\udca1",
}

export function ExtractionDashboard({
  bookId,
  events,
  progress,
  isConnected,
  isDone,
  isStarted = false,
  totalChapters = 0,
}: ExtractionDashboardProps) {
  const [entityStats, setEntityStats] = useState<GraphStats | null>(null)
  const [chapters, setChapters] = useState<ChapterInfo[]>([])
  const [dlqEntries, setDLQEntries] = useState<DLQEntry[]>([])
  const [showChapters, setShowChapters] = useState(false)
  const [retrying, setRetrying] = useState<number | null>(null)

  const latestEvent = events.length > 0 ? events[events.length - 1] : null
  const totalEntities = events.reduce((sum, e) => sum + e.entities_found, 0)
  const failedChapters = events.filter((e) => e.status === "failed").length
  const showWaiting = isConnected && !isStarted && events.length === 0

  // Poll for entity stats + chapter statuses during extraction
  const refreshData = useCallback(async () => {
    try {
      const [stats, bookDetail, dlq] = await Promise.all([
        getGraphStats(bookId),
        getBook(bookId),
        getDLQ(bookId).catch(() => ({ count: 0, entries: [] })),
      ])
      setEntityStats(stats)
      setChapters(bookDetail.chapters)
      setDLQEntries(dlq.entries)
    } catch {
      // silently ignore polling errors
    }
  }, [bookId])

  useEffect(() => {
    refreshData()
    if (isConnected && !isDone) {
      const interval = setInterval(refreshData, 8000) // Poll every 8s during extraction
      return () => clearInterval(interval)
    }
  }, [isConnected, isDone, refreshData])

  // Refresh once when done
  useEffect(() => {
    if (isDone) {
      refreshData()
    }
  }, [isDone, refreshData])

  const handleRetry = async (chapter: number) => {
    setRetrying(chapter)
    try {
      await retryDLQChapter(bookId, chapter)
      await refreshData()
    } finally {
      setRetrying(null)
    }
  }

  const handleRetryAll = async () => {
    setRetrying(-1)
    try {
      await retryAllDLQ()
      await refreshData()
    } finally {
      setRetrying(null)
    }
  }

  const doneChapters = chapters.filter((c) => c.status === "extracted").length
  const progressFromChapters = chapters.length > 0
    ? Math.round((doneChapters / chapters.length) * 100)
    : progress

  return (
    <div className="space-y-4">
      {/* ── Progress Bar ── */}
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          {isConnected ? (
            <Loader2 className="h-4 w-4 animate-spin text-indigo-400 shrink-0" />
          ) : isDone ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
          ) : null}

          <div className="flex-1 h-2.5 rounded-full bg-slate-800 overflow-hidden">
            {showWaiting ? (
              <div className="h-full w-full bg-indigo-500/30 animate-pulse rounded-full" />
            ) : (
              <div
                className={cn(
                  "h-full rounded-full transition-all duration-700",
                  isDone
                    ? failedChapters > 0 || dlqEntries.length > 0
                      ? "bg-amber-500"
                      : "bg-emerald-500"
                    : "bg-indigo-500",
                )}
                style={{ width: `${progressFromChapters}%` }}
              />
            )}
          </div>

          <span className="text-sm font-mono text-slate-300 tabular-nums shrink-0 min-w-[4rem] text-right">
            {showWaiting ? "..." : `${progressFromChapters}%`}
          </span>
        </div>

        <div className="flex items-center gap-4 text-xs text-slate-500">
          {showWaiting ? (
            <span>Preparing extraction pipeline...</span>
          ) : (
            <>
              <span className="font-medium text-slate-400">
                {doneChapters || latestEvent?.chapters_done || 0} / {chapters.length || totalChapters} chapters
              </span>
              {totalEntities > 0 && <span>{totalEntities} entities extracted</span>}
              {failedChapters > 0 && (
                <span className="flex items-center gap-1 text-red-400">
                  <XCircle className="h-3 w-3" />
                  {failedChapters} failed
                </span>
              )}
            </>
          )}
        </div>
      </div>

      {/* ── Entity Counts by Type ── */}
      {entityStats && entityStats.total_nodes > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(entityStats.nodes)
            .filter(([, count]) => count > 0)
            .sort(([, a], [, b]) => b - a)
            .map(([label, count]) => (
              <Badge
                key={label}
                variant="outline"
                className="text-xs px-2 py-0.5"
                style={{
                  borderColor: LABEL_COLORS[label] ?? "#475569",
                  color: LABEL_COLORS[label] ?? "#94a3b8",
                }}
              >
                {ENTITY_ICONS[label] || ""} {count} {label}{count > 1 ? "s" : ""}
              </Badge>
            ))}
        </div>
      )}

      {/* ── Chapter Table (collapsible) ── */}
      {chapters.length > 0 && (
        <div>
          <button
            onClick={() => setShowChapters((p) => !p)}
            className="flex items-center gap-2 text-xs text-slate-400 hover:text-slate-200 transition-colors mb-2"
          >
            {showChapters ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            Chapter Details
          </button>

          {showChapters && (
            <div className="rounded-lg border border-slate-800 overflow-hidden max-h-[300px] overflow-y-auto">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-slate-900 z-10">
                  <tr className="text-slate-500 uppercase tracking-wider">
                    <th className="text-left px-3 py-2 font-medium w-10">#</th>
                    <th className="text-left px-3 py-2 font-medium">Title</th>
                    <th className="text-center px-3 py-2 font-medium w-16">Status</th>
                    <th className="text-center px-3 py-2 font-medium w-20">Entities</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {chapters.map((ch) => (
                    <tr
                      key={ch.number}
                      className={cn(
                        "transition-colors",
                        ch.status === "extracted"
                          ? "text-slate-400"
                          : ch.status === "failed"
                            ? "text-red-400/80 bg-red-500/5"
                            : "text-slate-500",
                      )}
                    >
                      <td className="px-3 py-1.5 font-mono">{ch.number}</td>
                      <td className="px-3 py-1.5 truncate max-w-[200px]">{ch.title || `Chapter ${ch.number}`}</td>
                      <td className="px-3 py-1.5 text-center">
                        {STATUS_ICON[ch.status] || STATUS_ICON.pending}
                      </td>
                      <td className="px-3 py-1.5 text-center font-mono">
                        {ch.entity_count > 0 ? ch.entity_count : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── DLQ Section ── */}
      {dlqEntries.length > 0 && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-red-400" />
              <span className="text-xs font-medium text-red-400">
                {dlqEntries.length} Failed Chapter{dlqEntries.length > 1 ? "s" : ""}
              </span>
            </div>
            {dlqEntries.length > 1 && (
              <Button
                size="sm"
                variant="ghost"
                className="h-6 text-xs text-red-400 hover:text-red-300"
                onClick={handleRetryAll}
                disabled={retrying !== null}
              >
                {retrying === -1 ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <RefreshCw className="h-3 w-3 mr-1" />}
                Retry All
              </Button>
            )}
          </div>
          <div className="space-y-1.5">
            {dlqEntries.map((entry) => (
              <div
                key={`${entry.book_id}-${entry.chapter}`}
                className="flex items-center justify-between text-xs"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-mono text-red-400/80 shrink-0">Ch. {entry.chapter}</span>
                  <span className="text-slate-500 truncate">
                    {entry.error_type}: {entry.error_message}
                  </span>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-5 px-2 text-xs text-slate-400 hover:text-white shrink-0"
                  onClick={() => handleRetry(entry.chapter)}
                  disabled={retrying !== null}
                >
                  {retrying === entry.chapter ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <RefreshCw className="h-3 w-3" />
                  )}
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// Re-export simplified version for backward compatibility
export { ExtractionDashboard as ExtractionProgress }
```

**Step 2: Update types.ts**

Add `DLQEntry` to `frontend/lib/api/types.ts`:

```typescript
export interface DLQEntry {
  book_id: string
  chapter: number
  error_type: string
  error_message: string
  timestamp: string
  attempt_count: number
}
```

**Step 3: Commit**

```bash
git add frontend/components/shared/extraction-progress.tsx frontend/lib/api/types.ts
git commit -m "feat: rich extraction dashboard with progress, entity counts, chapter table, DLQ"
```

---

### Task 7: Update Library page to use new dashboard

**Files:**
- Modify: `frontend/app/(reader)/library/[id]/page.tsx` (lines 149-166)

**Step 1: Replace ExtractionProgress usage with ExtractionDashboard**

Update the import (change `ExtractionProgress` to `ExtractionDashboard`):

```typescript
import { ExtractionDashboard } from "@/components/shared/extraction-progress"
```

Replace the extraction card section (lines 149-166):

```tsx
      {extracting && (
        <Card>
          <CardContent className="pt-5 pb-4">
            <div className="flex items-center gap-2 mb-3">
              <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
              <h2 className="text-sm font-medium text-slate-400">Extraction in Progress</h2>
            </div>
            <ExtractionDashboard
              bookId={bookId}
              events={extraction.events}
              progress={extraction.progress}
              isConnected={extraction.isConnected}
              isDone={extraction.isDone}
              isStarted={extraction.isStarted}
              totalChapters={extraction.totalChapters}
            />
          </CardContent>
        </Card>
      )}
```

Also show the dashboard when book status is "extracted" (not just "extracting") to see final state:

Add after the extracting block:

```tsx
      {!extracting && book.status === "extracted" && (
        <Card>
          <CardContent className="pt-5 pb-4">
            <div className="flex items-center gap-2 mb-3">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              <h2 className="text-sm font-medium text-slate-400">Extraction Complete</h2>
            </div>
            <ExtractionDashboard
              bookId={bookId}
              events={[]}
              progress={100}
              isConnected={false}
              isDone={true}
              isStarted={true}
              totalChapters={book.total_chapters}
            />
          </CardContent>
        </Card>
      )}
```

**Step 2: Do same for Pipeline page**

Apply the same changes to `frontend/app/(pipeline)/pipeline/[id]/page.tsx` — same import change and component swap.

**Step 3: Verify in browser**

Navigate to `http://localhost:3500/library/{bookId}`. Should see:
- Progress bar with %
- Entity count badges
- Collapsible chapter table
- DLQ section if any failures

**Step 4: Commit**

```bash
git add "frontend/app/(reader)/library/[id]/page.tsx" "frontend/app/(pipeline)/pipeline/[id]/page.tsx"
git commit -m "feat: wire extraction dashboard into library and pipeline pages"
```

---

### Task 8: Add `getBook` to frontend API + fix imports

**Files:**
- Modify: `frontend/lib/api/books.ts` — ensure `getBook` is exported and returns `BookDetail`

**Step 1: Check and add missing exports**

Ensure `books.ts` exports:

```typescript
export function getBook(bookId: string): Promise<BookDetail> {
  return apiFetch(`/books/${bookId}`)
}

export function getDLQ(bookId?: string): Promise<{ count: number; entries: DLQEntry[] }> {
  const q = bookId ? `?book_id=${bookId}` : ""
  return apiFetch(`/admin/dlq${q}`)
}

export function retryDLQChapter(bookId: string, chapter: number): Promise<unknown> {
  return apiFetch(`/admin/dlq/retry/${bookId}/${chapter}`, { method: "POST" })
}

export function retryAllDLQ(): Promise<unknown> {
  return apiFetch(`/admin/dlq/retry-all`, { method: "POST" })
}
```

Import `DLQEntry` from types or define in books.ts.

**Step 2: Verify barrel exports**

Check `frontend/lib/api/index.ts` exports the new functions.

**Step 3: Commit**

```bash
git add frontend/lib/api/books.ts frontend/lib/api/index.ts frontend/lib/api/types.ts
git commit -m "feat: add DLQ and getBook API functions"
```

---

### Task 9: Final integration test

**Step 1: Rebuild Docker containers**

```bash
docker compose up -d --build backend worker frontend
```

**Step 2: Test Characters page**

Navigate to `http://localhost:3500/characters`. Verify only Character entities appear.

**Step 3: Test Wiki page**

Navigate to `http://localhost:3500/entity/Character/jacob`. Check no console errors about duplicate keys.

**Step 4: Test extraction dashboard**

Navigate to `http://localhost:3500/library/{bookId}`. Verify:
- Progress bar shows correct %
- Entity badges show counts by type
- Chapter table expands/collapses
- DLQ section shows any failed chapters

**Step 5: Final commit**

```bash
git add -A
git commit -m "chore: integration fixes from end-to-end testing"
```
