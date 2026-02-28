# WorldRAG V1 — Implementation Plan

**Date**: 2026-02-25
**Ref**: docs/plans/2026-02-25-worldrag-product-design.md
**Status**: Draft

---

## Overview

Refonte complète du frontend WorldRAG : passer du prototype actuel (4 pages, pas de shadcn, D3 force graph) à une plateforme commercialisable avec Sigma.js, lecteur annoté, chat amélioré, et timeline.

### Current State
- 4 pages: Dashboard, Books, Graph (D3 force-graph-2d), Chat
- No shadcn/ui (hand-rolled Tailwind components)
- No Zustand (raw useState everywhere)
- No route groups
- 2 components: NavLink, ForceGraph
- 1 API client file (lib/api.ts) with typed fetch

### Target State
- Route groups: (reader), (explorer)
- shadcn/ui for all primitives
- Zustand for global state (book context, graph filters, UI)
- Sigma.js (@react-sigma/core + graphology) replacing D3
- New pages: Annotated Reader, Timeline, Entity Wiki, Search, Library
- New backend endpoints: chapter text, chapter entities, entity wiki, SSE

---

## Phase 0 — Foundation (shadcn/ui + Zustand + Structure)

### 0.1 Install shadcn/ui
- `npx shadcn@latest init` in frontend/
- Configure: New York style, slate base, CSS variables
- Install core primitives: button, badge, input, select, dialog, sheet, hover-card, command, tabs, slider, scroll-area, collapsible, skeleton, sonner, dropdown-menu, tooltip, avatar, card, separator

### 0.2 Install Zustand
- `npm install zustand`
- Create stores:
  - `stores/book-store.ts`: selectedBookId, book, chapters, spoilerChapter
  - `stores/graph-store.ts`: graphData, filters (labels[], chapterRange), selectedNode, layout
  - `stores/ui-store.ts`: sidebarCollapsed, commandOpen

### 0.3 Restructure app/ to route groups
- Create `app/(reader)/` and `app/(explorer)/` directories
- Move: books/ → (reader)/library/, chat/ → (reader)/chat/
- New: (reader)/read/[bookId]/[chapter]/page.tsx (stub)
- Move: graph/ → (explorer)/graph/
- New: (explorer)/timeline/[bookId]/page.tsx (stub)
- New: (explorer)/entity/[type]/[name]/page.tsx (stub)
- New: (explorer)/search/page.tsx (stub)
- Update layout.tsx: new sidebar nav with route groups, global BookSelector

### 0.4 Shared components
- `components/shared/entity-badge.tsx`: colored badge per entity type, clickable
- `components/shared/book-selector.tsx`: global dropdown using Zustand bookStore
- `components/shared/search-command.tsx`: ⌘K command palette (shadcn Command)
- Update `lib/utils.ts`: keep LABEL_COLORS, add entity icon map
- Split `lib/api.ts` into `lib/api/books.ts`, `lib/api/graph.ts`, `lib/api/chat.ts`, `lib/api/admin.ts`

### Files to create/modify:
```
CREATE  frontend/components.json              (shadcn config)
CREATE  frontend/stores/book-store.ts
CREATE  frontend/stores/graph-store.ts
CREATE  frontend/stores/ui-store.ts
CREATE  frontend/components/shared/entity-badge.tsx
CREATE  frontend/components/shared/book-selector.tsx
CREATE  frontend/components/shared/search-command.tsx
CREATE  frontend/lib/api/books.ts
CREATE  frontend/lib/api/graph.ts
CREATE  frontend/lib/api/chat.ts
CREATE  frontend/lib/api/types.ts             (shared interfaces)
CREATE  frontend/app/(reader)/library/page.tsx
CREATE  frontend/app/(reader)/chat/page.tsx
CREATE  frontend/app/(reader)/read/[bookId]/[chapter]/page.tsx  (stub)
CREATE  frontend/app/(explorer)/graph/page.tsx
CREATE  frontend/app/(explorer)/timeline/[bookId]/page.tsx      (stub)
CREATE  frontend/app/(explorer)/entity/[type]/[name]/page.tsx   (stub)
CREATE  frontend/app/(explorer)/search/page.tsx                 (stub)
MODIFY  frontend/app/layout.tsx               (new sidebar + BookSelector)
MODIFY  frontend/app/page.tsx                 (use shadcn cards + Zustand)
DELETE  frontend/app/books/page.tsx           (moved to (reader)/library/)
DELETE  frontend/app/books/[id]/page.tsx      (moved to (reader)/library/[id]/)
DELETE  frontend/app/chat/page.tsx            (moved to (reader)/chat/)
DELETE  frontend/app/graph/page.tsx           (moved to (explorer)/graph/)
DELETE  frontend/components/graph/ForceGraph.tsx  (replaced by Sigma)
```

**Checkpoint**: `npm run build` passes, all pages render with shadcn components, BookSelector works globally.

---

## Phase 1 — Graph Explorer (Sigma.js)

### 1.1 Install Sigma.js stack
- `npm install sigma @react-sigma/core graphology graphology-layout-forceatlas2 graphology-types`

### 1.2 SigmaGraph component
- `components/graph/sigma-graph.tsx`: React wrapper using @react-sigma/core
  - Receives graphology Graph instance from parent
  - ForceAtlas2 layout with web worker
  - Node colors from LABEL_COLORS, size proportional to degree
  - Edge coloring by relationship type
  - Hover: highlight node + direct neighbors, fade rest
  - Click: dispatch to graphStore.selectedNode

### 1.3 GraphControls component
- `components/graph/graph-controls.tsx`:
  - Entity type filter toggles (using EntityBadge as toggle buttons)
  - Chapter range slider (shadcn Slider, dual handles)
  - Layout selector: ForceAtlas2 / Circular
  - Search input (filters nodes in graph)
  - Zoom controls (+/-/fit)
  - Stats: node count, edge count

### 1.4 Graph page refactor
- `app/(explorer)/graph/page.tsx`:
  - Uses Zustand graphStore for all state
  - Fetches subgraph based on filters
  - Renders SigmaGraph + GraphControls
  - Side panel (Sheet) for selected node details
  - Responsive: full width on mobile, side panel on desktop

### 1.5 Node detail panel
- `components/graph/node-detail-panel.tsx`:
  - Shows entity properties
  - For Characters: fetch profile, show skills/classes/events
  - "Open wiki page" link → /entity/{type}/{name}
  - "Expand neighbors" button → ego graph query

### Files:
```
CREATE  frontend/components/graph/sigma-graph.tsx
CREATE  frontend/components/graph/graph-controls.tsx
CREATE  frontend/components/graph/graph-legend.tsx
CREATE  frontend/components/graph/node-detail-panel.tsx
MODIFY  frontend/app/(explorer)/graph/page.tsx
MODIFY  frontend/stores/graph-store.ts
```

**Checkpoint**: Graph renders with Sigma.js, temporal slider filters nodes, entity type toggles work, node click shows detail panel.

---

## Phase 2 — Annotated Reader

### 2.1 Backend endpoints
- `GET /api/books/{id}/chapters/{num}/text` → returns chapter full text
- `GET /api/books/{id}/chapters/{num}/entities` → returns grounded entities with char offsets:
  ```json
  [{
    "entity_name": "Jake",
    "entity_type": "Character",
    "char_offset_start": 1234,
    "char_offset_end": 1238,
    "entity_id": "uuid"
  }]
  ```
- Add these routes in `backend/app/api/routes.py` (or new `reader_routes.py`)
- Query GROUNDED_IN relationships for the given chapter's chunks

### 2.2 AnnotatedText component
- `components/reader/annotated-text.tsx`:
  - Input: raw text string + annotation array (sorted by offset)
  - Algorithm: iterate text, split at annotation boundaries, wrap annotated spans
  - Each span: colored background per entity type, cursor pointer
  - onHover → HoverCard with entity name, type, description
  - onClick → navigate to entity wiki page or open detail dialog
  - Handle overlapping annotations (longest span wins)

### 2.3 ChapterNav component
- `components/reader/chapter-nav.tsx`:
  - Prev/Next chapter buttons
  - Chapter selector dropdown
  - Reading progress indicator

### 2.4 Reader page
- `app/(reader)/read/[bookId]/[chapter]/page.tsx`:
  - Fetches chapter text + entities in parallel
  - Renders AnnotatedText
  - Toggle modes: Annotated / Clean read / Entity focus (single type)
  - Chapter navigation
  - Sidebar: entity legend, list of entities found in this chapter

### 2.5 API client
- `lib/api/reader.ts`: getChapterText(), getChapterEntities()

### Files:
```
CREATE  backend/app/api/reader_routes.py
CREATE  frontend/components/reader/annotated-text.tsx
CREATE  frontend/components/reader/chapter-nav.tsx
CREATE  frontend/components/reader/reading-toolbar.tsx
CREATE  frontend/app/(reader)/read/[bookId]/[chapter]/page.tsx
CREATE  frontend/lib/api/reader.ts
MODIFY  backend/app/api/__init__.py           (register new routes)
MODIFY  backend/app/repositories/book_repo.py (add chapter text + entities queries)
```

**Checkpoint**: Can navigate to /read/{bookId}/{chapter}, see text with colored entity highlights, hover shows entity info.

---

## Phase 3 — Chat RAG Improvements

### 3.1 Backend: spoiler guard
- Add `max_chapter: int | None = None` to ChatRequest schema
- Filter vector search: `WHERE chap.number <= $max_chapter`
- Filter graph context: same filter

### 3.2 Backend: SSE streaming
- `GET /api/stream/chat` → SSE endpoint that streams LLM tokens
- Use asyncio generator with `yield` per token from Gemini streaming API
- FastAPI StreamingResponse with media_type="text/event-stream"

### 3.3 Frontend: Chat refactor
- Replace hand-rolled chat UI with shadcn components
- Add SpoilerGuard slider component (1..max_chapters)
- SSE streaming hook: `hooks/use-chat-stream.ts`
- Streaming message display (typing animation as tokens arrive)
- EntityBadge in answers (detect entity names, make clickable)
- SourceCard redesign (shadcn Collapsible + Card)
- Suggested questions after book selection

### Files:
```
MODIFY  backend/app/schemas/chat.py           (add max_chapter)
MODIFY  backend/app/services/chat_service.py  (filter by max_chapter)
CREATE  backend/app/api/stream_routes.py      (SSE endpoints)
CREATE  frontend/components/chat/spoiler-guard.tsx
CREATE  frontend/components/chat/source-card.tsx
CREATE  frontend/components/chat/chat-message.tsx
CREATE  frontend/hooks/use-chat-stream.ts
MODIFY  frontend/app/(reader)/chat/page.tsx
MODIFY  frontend/lib/api/chat.ts              (add max_chapter param)
```

**Checkpoint**: Chat works with spoiler guard, responses stream in real-time, entity mentions are clickable.

---

## Phase 4 — Timeline & Entity Wiki

### 4.1 Backend: enriched timeline
- Enrich `/api/graph/timeline/{book_id}` with level_changes, skill_acquisitions
- Add character filter param: `?character=Jake`
- New: `/api/graph/entity/{type}/{name}` → full entity wiki data (properties + all connections + appearance timeline)

### 4.2 Timeline components
- `components/timeline/timeline-view.tsx`: vertical timeline with chapter markers
- `components/timeline/event-card.tsx`: event with significance coloring
- `components/timeline/progression-card.tsx`: level-up, skill acquisition, class change

### 4.3 Timeline page
- `app/(explorer)/timeline/[bookId]/page.tsx`:
  - Book timeline: all events on vertical axis
  - Character filter: scope to one character
  - Significance filter: critical → minor
  - Click event → entity detail

### 4.4 Entity wiki page
- `app/(explorer)/entity/[type]/[name]/page.tsx`:
  - Entity header (name, type badge, description)
  - Properties section (all Neo4j properties)
  - Connections section (related entities, grouped by relationship type)
  - Timeline section (events involving this entity)
  - For Characters: full progression chart
  - Source references (chapters where entity appears)

### 4.5 Global search
- `app/(explorer)/search/page.tsx`:
  - Full-text entity search using existing endpoint
  - Filter by type, book
  - Results as cards with EntityBadge

### Files:
```
CREATE  backend/app/api/entity_routes.py
CREATE  frontend/components/timeline/timeline-view.tsx
CREATE  frontend/components/timeline/event-card.tsx
CREATE  frontend/components/timeline/progression-card.tsx
CREATE  frontend/app/(explorer)/timeline/[bookId]/page.tsx
CREATE  frontend/app/(explorer)/entity/[type]/[name]/page.tsx
CREATE  frontend/app/(explorer)/search/page.tsx
CREATE  frontend/lib/api/entity.ts
MODIFY  backend/app/api/routes.py             (enrich timeline, add entity wiki)
MODIFY  backend/app/repositories/entity_repo.py (wiki queries)
```

**Checkpoint**: Timeline shows events by chapter, entity wiki pages show full profiles, search works.

---

## Phase 5 — SSE Extraction Progress & Polish

### 5.1 Backend: extraction SSE
- `GET /api/stream/extraction/{book_id}` → SSE with progress events:
  ```
  data: {"chapter": 3, "total": 26, "status": "extracting", "pass": "characters"}
  data: {"chapter": 3, "total": 26, "status": "done", "entities_found": 42}
  ```
- arq worker publishes progress to Redis pub/sub
- SSE endpoint subscribes to Redis channel

### 5.2 ExtractionProgress component
- `components/shared/extraction-progress.tsx`:
  - SSE hook connects to extraction stream
  - Shows progress bar per chapter
  - Real-time entity count
  - Log of passes completed

### 5.3 Library page upgrade
- Enhanced book cards (not table) with cover placeholder, stats
- Extraction progress inline
- Book detail page with chapter list + stats

### 5.4 Dashboard refactor
- Use shadcn Cards for stats
- Recent activity feed
- Quick actions (upload, explore, chat)

### 5.5 Responsive & polish
- Mobile sidebar drawer
- Loading skeletons everywhere
- Error boundaries
- Keyboard shortcuts (⌘K search, Esc close panels)
- Toast notifications (sonner)

### Files:
```
CREATE  backend/app/api/stream_routes.py      (SSE extraction)
CREATE  frontend/components/shared/extraction-progress.tsx
CREATE  frontend/hooks/use-sse.ts
MODIFY  frontend/app/(reader)/library/page.tsx (enhanced cards)
MODIFY  frontend/app/page.tsx                  (dashboard refactor)
MODIFY  frontend/app/layout.tsx                (responsive sidebar)
```

**Checkpoint**: Full V1 working — all features integrated, responsive, polished.

---

## Execution Strategy

Execute phases sequentially. Each phase has a build checkpoint.
Phases can use parallel agents for independent file creation within a phase.

**Total estimated files**: ~35 new, ~15 modified, ~5 deleted
**Dependencies**: Phase 0 must complete first. Phases 1-4 can partially overlap. Phase 5 is polish.

## Risk Mitigation
- shadcn/ui init may conflict with existing Tailwind config → verify CSS variables
- Sigma.js SSR: needs 'use client' + dynamic import (no SSR for WebGL)
- Route group migration: verify all internal links updated
- Backend endpoints: add incrementally, test with curl before frontend integration
