# Extraction UI Redesign — Sub-project 1

## Goal

Replace the current flat extraction dashboard with a guided 5-step pipeline (Upload → Configure → Extract → Review → Explore), add transversal UI infrastructure (TanStack Query, SSE reconnection, shared components), and create 4 backend endpoints for post-extraction entity/relation editing.

## Users

- Primary (now): single power user piloting extraction and inspecting results
- Target (future): non-technical users (readers, authors, editors) browsing the constructed KG
- Design must be power-user efficient today and intuitive enough for non-technical users tomorrow

## Architecture

### Data Fetching: TanStack Query v5

Replace all manual `apiFetch` calls in components with TanStack Query hooks. The `apiFetch` function in `lib/api/client.ts` remains as the transport layer — TanStack Query wraps it.

**Query hooks** (new file per domain):

- `hooks/use-books.ts`:
  - `useBooks(projectSlug)` — `GET /projects/{slug}/books`, staleTime: 30s
  - `useBookDetail(bookId)` — `GET /books/{book_id}`, staleTime: 30s
  - `useBookStats(bookId)` — `GET /books/{book_id}/stats`, staleTime: 60s
  - `useBookJobs(bookId)` — `GET /books/{book_id}/jobs`, refetchInterval: 5s when extracting

- `hooks/use-extraction.ts`:
  - `useExtractionProgress(bookId)` — SSE hook (see below), not a query
  - `useTriggerExtraction()` — mutation, `POST /books/{id}/extract/v4`
  - `useRetryChapter()` — mutation, `POST /admin/dlq/retry/{book_id}/{chapter}`
  - `useDLQEntries(bookId)` — `GET /admin/dlq?book_id={id}`, staleTime: 10s

- `hooks/use-graph-mutations.ts`:
  - `useRenameEntity()` — mutation, `PATCH /graph/entity/{id}`
  - `useDeleteEntity()` — mutation, `DELETE /graph/entity/{id}`, invalidates graph queries
  - `useMergeEntities()` — mutation, `POST /graph/entities/merge`, invalidates graph queries
  - `useDeleteRelation()` — mutation, `DELETE /graph/relationship/{id}`

**QueryClientProvider** added to `app/layout.tsx`, wrapping existing ThemeProvider.

**Query client config:**
```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      retry: 3,
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30_000),
    },
  },
})
```

### SSE Hook with Reconnection

Replace `hooks/use-extraction-stream.ts` with a robust implementation.

**Interface:**
```typescript
type SSEStatus = 'connecting' | 'connected' | 'reconnecting' | 'disconnected'

function useExtractionSSE(bookId: string | null): {
  status: SSEStatus
  chapters: Map<number, ChapterProgress>
  totalEntities: number
  error: string | null
}
```

**Reconnection logic:**
- On connection loss: backoff 1s → 2s → 4s → 8s → 16s → 30s (capped)
- On `error` event from server: stop reconnecting, surface error
- On `done` event: close connection, invalidate book queries
- Keepalive timeout: if no event for 60s, trigger reconnect
- Expose `status` for SSEIndicator component

### URL State: nuqs

All pipeline state persisted in search params via `nuqs` (type-safe, Next.js App Router compatible).

```typescript
// In pipeline layout
const [step, setStep] = useQueryState('step', parseAsStringEnum(['upload', 'configure', 'extract', 'review', 'explore']).withDefault('upload'))
const [bookId, setBookId] = useQueryState('book')
```

Benefits: deep-linkable, survives refresh, shareable.

### New Dependencies

| Package | Version | Purpose | Bundle impact |
|---------|---------|---------|---------------|
| `@tanstack/react-query` | ^5 | Data fetching + cache | ~13KB gzip |
| `nuqs` | ^2 | URL state for Next.js | ~3KB gzip |

`framer-motion` already present as `motion` ^12.34.3 in package.json. No new animation library needed.

`swr` (currently in package.json) will be removed after migration — nothing uses it currently.

---

## Shared Components

### `<StepIndicator />`

Horizontal progress bar showing pipeline stages.

**File:** `components/pipeline/step-indicator.tsx`

**Props:**
```typescript
type StepStatus = 'completed' | 'active' | 'upcoming'
interface Step { label: string; status: StepStatus }
interface StepIndicatorProps {
  steps: Step[]
  onStepClick: (index: number) => void
}
```

**Behavior:**
- Completed steps: check icon, accent color, clickable (navigates back)
- Active step: pulsing dot, bold label
- Upcoming steps: gray, not clickable
- Connecting line between steps: solid for completed, dashed for upcoming

### `<ErrorState />`

**File:** `components/ui/error-state.tsx`

**Props:**
```typescript
interface ErrorStateProps {
  title: string
  message?: string
  error?: Error | null
  onRetry?: () => void
}
```

**Renders:** Icon + title + message + "Retry" button (if onRetry provided) + collapsible "Technical details" showing `error.message`.

### `<EmptyState />`

**File:** `components/ui/empty-state.tsx`

**Props:**
```typescript
interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description?: string
  action?: { label: string; onClick: () => void }
}
```

### `<StatusBadge />`

Already exists at `components/shared/status-badge.tsx`. Verify it covers all statuses: `pending`, `ingested`, `extracting`, `extracted`, `partial`, `error`, `error_quota`, `cost_ceiling_hit`, `embedded`. Add any missing statuses.

### `<ConfidenceBar />`

**File:** `components/ui/confidence-bar.tsx`

**Props:**
```typescript
interface ConfidenceBarProps {
  value: number // 0.0 - 1.0
  size?: 'sm' | 'md'
}
```

**Renders:** Thin horizontal bar. Color: red (< 0.3) → orange (0.3-0.7) → green (> 0.7). Width proportional to value.

### `<SSEIndicator />`

**File:** `components/ui/sse-indicator.tsx`

**Props:**
```typescript
interface SSEIndicatorProps {
  status: 'connecting' | 'connected' | 'reconnecting' | 'disconnected'
}
```

**Renders:** Small colored dot (green/orange-pulsing/red) with tooltip showing status text.

---

## Pipeline Flow

### Route Structure

The pipeline lives at `/projects/[slug]/books/[bookId]/extraction/`.

The current route `frontend/app/projects/[slug]/books/[bookId]/extraction/page.tsx` becomes the pipeline container. It reads `?step=` from URL and renders the appropriate step component.

```
/projects/[slug]/books/[bookId]/extraction?step=upload
/projects/[slug]/books/[bookId]/extraction?step=configure
/projects/[slug]/books/[bookId]/extraction?step=extract
/projects/[slug]/books/[bookId]/extraction?step=review&tab=entities
/projects/[slug]/books/[bookId]/extraction?step=explore
```

For new books (no bookId yet), the upload step lives at:
```
/projects/[slug]/books/new
```
After upload completes, redirect to `/projects/[slug]/books/[newBookId]/extraction?step=configure`.

### Pipeline Layout

**File:** `components/pipeline/pipeline-layout.tsx`

Wraps all step content. Renders:
1. StepIndicator at top
2. Step content below
3. Handles step transitions (animate with motion)

### Step 1: Upload

**File:** `components/extraction/steps/upload-step.tsx`

**UI:**
- If project has no books: full-width drag & drop zone with icon + "Drop your epub, pdf, or txt file here"
- If project has books: compact book list (BookCard grid) + "Add a book" button that expands the drop zone
- On file drop: show filename + spinner, call `POST /projects/{slug}/books`
- On success: show detected title, chapter count, cover thumbnail (from project covers endpoint)
- Auto-transition to Configure after 1.5s delay (with "Configure extraction" button for immediate transition)

**Data:**
- `useBooks(projectSlug)` for existing books
- `useMutation` for upload

### Step 2: Configure

**File:** `components/extraction/steps/configure-step.tsx`

**UI:**
- Book info bar at top: cover thumbnail + title + chapter count
- Genre selector: 3 cards (LitRPG, Fantasy, Sci-Fi) with icon + label. Selected = accent border. Extensible for more genres.
- Language toggle: FR / EN (pill toggle)
- Provider selector: shadcn Select with options:
  - "Gemini 2.5 Flash (free)" — default
  - "DeepSeek V3.2 via OpenRouter ($0.26/M tokens)"
  - "Ollama local (qwen3:32b)" — only if local provider configured
- Advanced section (shadcn Collapsible): chapter multi-select checklist for partial extraction
- Primary CTA button: "Start extraction" (full width, prominent)

**Data:**
- `useBookDetail(bookId)` for chapter list
- `useTriggerExtraction()` mutation on CTA click

### Step 3: Extract (Progress)

**File:** `components/extraction/steps/extract-step.tsx`

**Layout:** 2 columns (lg breakpoint), stacked on mobile.

**Left column (2/3): Chapter list**

Component: `components/extraction/chapter-progress-list.tsx`

Each chapter row shows:
- Chapter number + title (truncated)
- Status icon: spinner (extracting), check (done), X (failed), clock (pending)
- Entity count badge (when done)
- Duration (when done)
- Retry button (when failed, calls `useRetryChapter()`)

Expand a chapter row → inline preview of extracted entities as small badges.

Active chapter (currently extracting) has animated progress indicator.

**Right column (1/3): Live stats panel**

Component: `components/extraction/extraction-live-stats.tsx`

- Total entities counter (animated increment via motion)
- Donut chart by entity type (recharts, uses ENTITY_HEX colors)
- Progress: "12/45 chapters" with progress bar
- Elapsed time / estimated remaining
- Cost badge (if provider is paid): "$0.12"
- SSEIndicator component at bottom

**Bottom bar:**
- "Stop extraction" button (secondary, stops after current chapter)

**Data:**
- `useExtractionSSE(bookId)` for real-time progress
- `useBookJobs(bookId)` as polling fallback
- `useDLQEntries(bookId)` for failed chapters

### Step 4: Review

**File:** `components/extraction/steps/review-step.tsx`

**Layout:** Full width with 3 tabs (shadcn Tabs).

**Tab 1: Entities**

Component: `components/extraction/review/entity-review-table.tsx`

- shadcn Table with columns: checkbox, name, type (badge), confidence (ConfidenceBar), mentions, chapters (first-last)
- Sortable by any column (click header)
- Filter bar above table:
  - Entity type multi-select (checkboxes)
  - Confidence slider (0-1 range, filters below threshold)
  - Text search (filters by name)
- Entities with confidence < 0.5: row background tinted orange
- Row actions (dropdown menu):
  - "Rename" → inline edit (input replaces text, Enter to confirm)
  - "Delete" → confirmation dialog
- Bulk actions (when checkboxes selected):
  - "Merge selected" (2+ selected) → dialog asking which name to keep
  - "Delete selected" → confirmation dialog with count

**Data:**
- Entity list from `GET /graph/entities?book_id={id}&label={type}` (paginated, one call per type)
- Mutations: `useRenameEntity()`, `useDeleteEntity()`, `useMergeEntities()`
- On mutation success: invalidate entity queries + `useBookStats`

**Tab 2: Relations**

Component: `components/extraction/review/relation-review-table.tsx`

- Table columns: source, relation type (badge), target, chapter, sentiment (color dot)
- Filter by relation type
- Row action: "Delete" → confirmation dialog
- Data: from `GET /graph/subgraph/{book_id}` edges

**Tab 3: Problems**

Component: `components/extraction/review/problems-panel.tsx`

Three sections (collapsible):

1. **Failed chapters** (from DLQ):
   - Chapter number + error type + error message
   - "Retry" button per chapter
   - "Retry all" button

2. **Potential duplicates** (computed client-side from entity list):
   - Pairs of entities with similar names (case-insensitive prefix match or Levenshtein < 3)
   - "Merge" button per pair

3. **Orphan entities** (entities with 0 relations):
   - Entity name + type
   - "Delete" or "Keep" buttons

### Step 5: Explore

**File:** `components/extraction/steps/explore-step.tsx`

Minimal — renders a CTA card:
- "Your Knowledge Graph is ready" + entity/relation counts
- "Open Graph Explorer" button → navigates to `/projects/[slug]/graph?book={bookId}`
- "Export" dropdown: Cypher / JSON-LD / CSV (calls existing export endpoints)

---

## Backend Endpoints

### `PATCH /graph/entity/{entity_id}`

**File:** `backend/app/api/graph.py` (add to existing router)

**Request body (Pydantic):**
```python
class EntityUpdate(BaseModel):
    name: str | None = None
    canonical_name: str | None = None
    description: str | None = None
```

**Logic:**
1. Validate entity exists: `MATCH (e) WHERE elementId(e) = $id RETURN e`
2. Build SET clause from non-None fields
3. Execute: `MATCH (e) WHERE elementId(e) = $id SET e.name = $name, ... RETURN e`
4. Return updated properties

**Response:** `{"id": str, "labels": list[str], "updated_properties": list[str]}`

**Errors:** 404 if entity not found, 400 if no fields provided

### `DELETE /graph/entity/{entity_id}`

**File:** `backend/app/api/graph.py`

**Logic:**
1. Count relationships: `MATCH (e)-[r]-() WHERE elementId(e) = $id RETURN count(r) as rel_count`
2. Detach delete: `MATCH (e) WHERE elementId(e) = $id DETACH DELETE e`

**Response:** `{"deleted": true, "relationships_removed": int}`

**Errors:** 404 if entity not found

### `POST /graph/entities/merge`

**File:** `backend/app/api/graph.py`

**Request body:**
```python
class EntityMergeRequest(BaseModel):
    source_id: str  # entity to remove
    target_id: str  # entity to keep
```

**Logic:**
1. Validate both entities exist
2. Read source entity properties (aliases, name)
3. Add source name + aliases to target's aliases array: `SET target.aliases = target.aliases + $new_aliases`
4. Transfer all relationships from source to target via APOC or procedural Cypher:
   - Use `apoc.refactor.mergeNodes([target, source], {properties: 'combine'})` if APOC is available
   - Fallback without APOC: iterate relationship types programmatically in Python (read all rels from source, recreate on target, delete originals) — cannot use dynamic rel types in pure Cypher CREATE
5. Delete source: `DETACH DELETE source`

**Response:** `{"merged_into": str, "aliases_added": list[str], "relationships_transferred": int}`

**Errors:** 404 if either entity not found, 400 if source_id == target_id

### `DELETE /graph/relationship/{relationship_id}`

**File:** `backend/app/api/graph.py`

**Logic:**
1. `MATCH ()-[r]->() WHERE elementId(r) = $id DELETE r`

**Response:** `{"deleted": true}`

**Errors:** 404 if relationship not found

---

## Files Created / Modified / Deleted

### Created (frontend — 20 files)

```
# Infrastructure
hooks/use-books.ts
hooks/use-extraction.ts
hooks/use-graph-mutations.ts
lib/query-client.ts

# Shared components
components/pipeline/step-indicator.tsx
components/pipeline/pipeline-layout.tsx
components/ui/error-state.tsx
components/ui/empty-state.tsx          # may already exist, check and extend
components/ui/confidence-bar.tsx
components/ui/sse-indicator.tsx

# Pipeline steps
components/extraction/steps/upload-step.tsx
components/extraction/steps/configure-step.tsx
components/extraction/steps/extract-step.tsx
components/extraction/steps/review-step.tsx
components/extraction/steps/explore-step.tsx

# Step sub-components
components/extraction/chapter-progress-list.tsx
components/extraction/extraction-live-stats.tsx
components/extraction/review/entity-review-table.tsx
components/extraction/review/relation-review-table.tsx
components/extraction/review/problems-panel.tsx
```

### Created (backend — 1 file modified)

```
backend/app/api/graph.py              # Add 4 endpoints to existing router
backend/app/schemas/graph.py          # EntityUpdate, EntityMergeRequest models (if not exists)
```

### Modified

```
frontend/app/layout.tsx               # Add QueryClientProvider
frontend/app/projects/[slug]/books/[bookId]/extraction/page.tsx  # Pipeline container
frontend/package.json                 # Add @tanstack/react-query, nuqs; remove swr
```

### Deleted

```
frontend/stores/graph-store.ts                          # Unused
frontend/components/extraction/dashboard.tsx             # Replaced by pipeline steps
frontend/app/projects/[slug]/books/[bookId]/extraction/dashboard.tsx  # Replaced
frontend/hooks/use-extraction-stream.ts                 # Replaced by use-extraction.ts
```

### Preserved (not touched)

```
frontend/components/extraction/extraction-donut.tsx     # Reused in extraction-live-stats
frontend/components/graph/*                             # Sub-project 2
frontend/components/ontology/*                          # Sub-project 3
frontend/components/chat/*                              # Out of scope
frontend/components/reader/*                            # Out of scope
frontend/lib/api/client.ts                              # Transport layer, unchanged
frontend/lib/constants.ts                               # ENTITY_HEX colors, unchanged
```

---

## Out of Scope

- Graph Explorer redesign (sub-project 2)
- Ontology Viewer redesign (sub-project 3)
- Extraction versioning / comparison between runs
- Mobile-first layout (responsive: yes, mobile-first: no)
- i18n (UI stays English, book content can be any language)
- Auth UI (API key only, no login screen)
