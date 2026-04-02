# Graph Explorer Redesign — Sub-project 2

## Goal

Replace the monolithic graph explorer (342L page + 305L sigma component) with a modular, performant architecture: server-side filtering, progressive node loading, URL-persisted filters, keyboard shortcuts, color cache, and proper loading/error/empty states.

## Users

Same as sub-project 1: power user now, non-technical users later.

## Architecture

### Data Flow

**Initial load:** Frontend calls `GET /graph/subgraph/{book_id}?label={labels}&chapter={ch}&limit=100` with URL filters. TanStack Query caches the response keyed by `["graph", "subgraph", bookId, filters]`. Graphology Graph is built from the response.

**Expand on-demand:** Double-click a node → call `GET /graph/neighbors/{entity_id}?depth=1&limit=50` → merge new nodes/edges into the existing graphology Graph (additive, no full reload).

**Search:** `GET /graph/search?q={query}&book_id={bookId}` → dropdown results → select → center camera on node + load neighbors if not in graph.

**Filter change:** URL params update via nuqs → TanStack Query refetches → graphology Graph rebuilt from scratch (filters are server-side, not client-side).

### URL State (nuqs)

```
/projects/[slug]/graph?book=abc&labels=Character,Skill&chapter=5&search=Jake&node=4:abc:123
```

Parameters:
- `book` — selected book ID
- `labels` — comma-separated entity type filter (empty = all)
- `chapter` — max chapter filter (empty = all)
- `search` — current search query
- `node` — selected node ID (opens detail panel)

### TanStack Query Hook

New file `hooks/use-graph.ts`:

```typescript
useSubgraph(bookId, filters: { labels?: string[], chapter?: number })
```
- Query key: `["graph", "subgraph", bookId, labels, chapter]`
- Calls `GET /graph/subgraph/{book_id}?label={label}&chapter={chapter}&limit=1000`
- staleTime: 5 minutes (graph data changes rarely)
- Returns `SubgraphData` ({ nodes, edges })

```typescript
useNeighbors(entityId: string | null)
```
- Query key: `["graph", "neighbors", entityId]`
- Calls `GET /graph/neighbors/{entity_id}?depth=1&limit=50`
- enabled: `!!entityId` (only fires when explicitly triggered)
- Returns `SubgraphData`

```typescript
useGraphSearch(bookId, query: string)
```
- Query key: `["graph", "search", bookId, query]`
- Calls `GET /graph/search?q={query}&book_id={bookId}&limit=10`
- enabled: `query.length >= 2`
- staleTime: 30s
- Returns `GraphNode[]`

### No Backend Changes

All required endpoints already exist:
- `GET /graph/subgraph/{book_id}` — with `label?`, `chapter?`, `limit?` params
- `GET /graph/neighbors/{entity_id}` — with `depth?`, `limit?` params
- `GET /graph/search` — with `q`, `book_id?`, `label?`, `limit?` params
- `GET /graph/stats` — with `book_id?` param
- `GET /graph/wiki/{entity_type}/{entity_name}` — for detail panel links

---

## Components

### `graph-container.tsx` — Orchestrator

**File:** `frontend/components/graph/graph-container.tsx`

**Props:**
```typescript
interface GraphContainerProps {
  projectSlug: string
  bookId: string
}
```

**Responsibilities:**
- Reads URL state via nuqs: `labels`, `chapter`, `search`, `node`
- Calls `useSubgraph(bookId, { labels, chapter })` for data
- Maintains a `graphology.MultiDirectedGraph` instance in useRef
- Rebuilds graph from subgraph data on filter change
- Merges neighbor data into existing graph on expand (additive)
- Manages selected node state (synced to URL `node` param)
- Keyboard shortcuts via useEffect:
  - `+`/`=`: zoom in
  - `-`: zoom out
  - `f`: fit to screen
  - `Escape`: close detail panel
- Exposes zoom/fit functions via refs passed to canvas
- Loading/error/empty states using shared components from sub-project 1

**Layout:**
```
┌──────────────────────────────────────────────┐
│ graph-toolbar                                │
├──────────────────────────────────┬───────────┤
│                                  │ detail    │
│  graph-canvas                    │ panel     │
│  (sigma.js)                      │ (node)    │
│                                  │           │
├──────────────────────────────────┴───────────┤
│ graph-legend (floating, bottom-left)         │
└──────────────────────────────────────────────┘
```

### `graph-canvas.tsx` — Sigma.js Pure Renderer

**File:** `frontend/components/graph/graph-canvas.tsx`

**Props:**
```typescript
interface GraphCanvasProps {
  graph: MultiDirectedGraph
  selectedNodeId: string | null
  highlightNodeId: string | null
  onNodeClick: (nodeId: string) => void
  onNodeDoubleClick: (nodeId: string) => void
  onCanvasClick: () => void
  onZoomIn?: (fn: () => void) => void
  onZoomOut?: (fn: () => void) => void
  onFit?: (fn: () => void) => void
  onFocusNode?: (fn: (nodeId: string) => void) => void
}
```

**Responsibilities:**
- Initializes Sigma.js renderer on mount with the provided graphology Graph
- ForceAtlas2 layout with auto-stop on convergence (not fixed 3s timeout):
  - Run layout, check energy delta every 500ms
  - Stop when delta < threshold or max 5s
- Node reducer:
  - Color: `ENTITY_HEX[label]` via a `Map<string, string>` cache (built once per render, not per frame)
  - Size: `Math.max(3, Math.sqrt(degree) * 2)`
  - Label visibility: show when camera ratio < 0.4 OR node is hovered/selected
  - Selected node: ring highlight
  - Hovered node: brighten, dim non-neighbors
- Edge reducer:
  - Default: 50% opacity
  - Hovered/selected node: full opacity on connected edges, 10% on others
- Exposes imperative methods via callback props (zoom, fit, focusNode)
- `aria-label="Knowledge graph visualization"` on container div
- Cleans up Sigma instance on unmount

**Perf fixes vs current sigma-graph.tsx:**
- Color map built once per data change, not per node render
- No CSS variable reading in hot path (pre-resolve on mount)
- ForceAtlas2 convergence-based stop instead of fixed timeout

### `graph-toolbar.tsx` — Filters + Search + Actions

**File:** `frontend/components/graph/graph-toolbar.tsx`

**Props:**
```typescript
interface GraphToolbarProps {
  // Book selector
  books: Array<{ id: string; title: string }>
  selectedBookId: string
  onBookChange: (bookId: string) => void
  // Filters
  availableLabels: string[]
  activeLabels: string[]
  onLabelsChange: (labels: string[]) => void
  maxChapter: number
  chapterFilter: number | null
  onChapterChange: (chapter: number | null) => void
  // Search
  bookId: string
  onSearchSelect: (nodeId: string) => void
  // Stats
  nodeCount: number
  edgeCount: number
  // Zoom
  onZoomIn: () => void
  onZoomOut: () => void
  onFit: () => void
}
```

**Layout:** Horizontal bar, responsive (wraps on mobile).

**Sections (left to right):**
1. Book selector (Select, hidden if single book)
2. Entity type badges — clickable toggles, colored with ENTITY_HEX, active = filled, inactive = outline
3. Chapter filter — Select with "All chapters" default + chapter numbers
4. Separator
5. Search input — debounced 300ms, dropdown with results, keyboard nav (up/down/enter/escape)
6. Separator
7. Stats: "{N} nodes · {M} edges" in muted text
8. Zoom buttons: +, fit, - (with `aria-label`)

**Search implementation:**
- Uses `useGraphSearch(bookId, query)` hook
- Dropdown positioned below input
- Arrow up/down to navigate, Enter to select, Escape to close
- Selected result calls `onSearchSelect(nodeId)`

### `graph-detail-panel.tsx` — Node Detail Sidebar

**File:** `frontend/components/graph/graph-detail-panel.tsx`

**Props:**
```typescript
interface GraphDetailPanelProps {
  nodeId: string
  bookId: string
  projectSlug: string
  graph: MultiDirectedGraph  // to read neighbors/edges locally
  onClose: () => void
  onExpandNeighbors: (nodeId: string) => void
}
```

**Layout:** Right sidebar, w-80, slides in from right (motion animate).

**Content:**
- Header: entity name (from graph node attrs) + type Badge + close button (X)
- Description (if available on node)
- Tabs (shadcn Tabs):
  - **Relations**: edges grouped by type from the graphology Graph instance (no extra API call). Each group collapsible, shows source/target with direction arrow.
  - **Appearances**: chapter list from node attributes (if available)
- Actions:
  - "Expand neighbors" button → calls `onExpandNeighbors(nodeId)`
  - "View wiki" link → `/projects/{slug}/graph` wiki route or opens wiki endpoint
  - "Chat about" link → `/projects/{slug}/chat?q={name}`

### `graph-legend.tsx` — Floating Legend

**File:** `frontend/components/graph/graph-legend.tsx`

**Props:**
```typescript
interface GraphLegendProps {
  visibleTypes: Array<{ type: string; count: number }>
  activeLabels: string[]
  onToggle: (type: string) => void
}
```

**Position:** Absolute, bottom-left of the graph canvas area.

**Renders:** Compact list of entity types visible in the graph:
- Colored dot (ENTITY_HEX) + type label + count
- Each row clickable — toggles the label filter (syncs with toolbar)
- Collapsible header "Legend" for small screens

---

## Page Rewrite

**File:** `frontend/app/projects/[slug]/graph/page.tsx`

Simplified from 342L to ~40L. Becomes a thin wrapper:

```typescript
"use client"

import { use, useMemo } from "react"
import { useQueryState } from "nuqs"
import { useBooks } from "@/hooks/use-books"
import { GraphContainer } from "@/components/graph/graph-container"
import { Skeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/shared/empty-state"

export default function GraphPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params)
  const [bookId, setBookId] = useQueryState("book")
  const { data: books, isLoading } = useBooks(slug)

  // Auto-select first book if none selected
  // ... minimal logic, delegates to GraphContainer
}
```

All graph logic lives in `GraphContainer`, not in the page.

---

## Files Created / Modified / Deleted

### Created (5 files)
```
frontend/hooks/use-graph.ts                           # TanStack Query hooks
frontend/components/graph/graph-container.tsx          # Orchestrator
frontend/components/graph/graph-canvas.tsx             # Sigma.js renderer
frontend/components/graph/graph-toolbar.tsx            # Filters + search + zoom
frontend/components/graph/graph-legend.tsx             # Floating legend
```

### Modified (2 files)
```
frontend/components/graph/graph-detail-panel.tsx       # Refactored (new props, reads from graphology)
frontend/app/projects/[slug]/graph/page.tsx            # Simplified to thin wrapper
```

### Deleted (4 files)
```
frontend/components/graph/sigma-graph.tsx              # Replaced by graph-canvas.tsx
frontend/components/graph/graph-filters.tsx            # Merged into graph-toolbar.tsx
frontend/components/graph/graph-search.tsx             # Merged into graph-toolbar.tsx
frontend/components/graph/graph-stats-bar.tsx          # Merged into graph-toolbar.tsx
frontend/components/graph/graph-book-selector.tsx      # Merged into graph-toolbar.tsx
```

### Preserved
```
frontend/hooks/use-graph-mutations.ts                  # Already done in sub-project 1
frontend/lib/api/graph.ts                              # API client unchanged
frontend/lib/constants.ts                              # ENTITY_HEX unchanged
```

---

## Out of Scope

- Ontology viewer redesign (sub-project 3)
- 3D graph mode
- Advanced keyboard shortcuts (1-9 type filter, arrow navigation)
- Graph comparison between books
- Graph editing from the explorer (editing is in the Review step)
