# WorldRAG Product Design — V1 Commercial Platform

**Date**: 2026-02-25
**Status**: Approved
**Target**: Readers (V1) → Authors → Publishers (V2+)

---

## 1. Vision

WorldRAG transforms any fiction novel into an interactive, explorable knowledge graph. Upload an epub, get a living wiki of the universe — characters, skills, events, locations, factions — with a chat assistant that answers questions grounded in the source text.

**Tagline**: "The Wikipedia of your favorite book, auto-generated."

**V1 Target**: LitRPG / progression fantasy readers who want to track complex game systems, character progressions, and world lore across long series.

## 2. Target Users

| Persona | V1 | V2 | Core Need |
|---------|----|----|-----------|
| **Reader** | Primary | Primary | Explore universe, ask questions, track progression |
| **Author** | — | Secondary | Verify continuity, track worldbuilding, detect inconsistencies |
| **Publisher** | — | Tertiary | Quality review, metadata extraction, series management |

## 3. Competitive Landscape

| Tool | Strength | WorldRAG Differentiator |
|------|----------|----------------------|
| Neo4j LLM Graph Builder | Generic text→graph, zero config | Fiction-specific ontology, temporality, progression tracking |
| Microsoft GraphRAG | Community summaries, dual retrieval | Chapter-based temporal KG, spoiler-free queries |
| BookNLP | Literary NLP (coreference, dialogue attribution) | Interactive UI, chat RAG, real-time extraction |
| Prodigy / Label Studio | NER annotation overlay on text | Auto-extraction + annotation view (no manual labeling) |
| Aeon Timeline | Fiction timeline tool for writers | Auto-generated timeline from extracted events |
| Obsidian (fiction workflow) | Manual bidirectional linking | Fully automated, no manual work |

**Key gap exploited**: No tool combines fiction-aware extraction + temporal KG + interactive graph + annotated reader + chat RAG. The LitRPG/progression fantasy niche is completely unserved.

## 4. Architecture

### 4.1 High-Level

```
Frontend (Next.js 16 + shadcn/ui + Sigma.js)
  ├── (reader)   → Library, Reader, Chat
  ├── (explorer) → Graph, Timeline, Wiki, Search
  ├── (admin)    → Costs, DLQ, Monitoring (V2)
  └── (studio)   → Ontology, Prompts, Corrections (V2)

Backend (FastAPI, existing + extended)
  ├── /api/books    → CRUD, ingestion, extraction
  ├── /api/graph    → Search, subgraph, entities, timeline
  ├── /api/chat     → Hybrid RAG query
  ├── /api/stream   → SSE extraction progress (NEW)
  └── /api/admin    → Costs, DLQ

Infrastructure (Docker Compose)
  Neo4j │ Redis │ PostgreSQL │ arq Workers │ LangFuse
```

### 4.2 Frontend Structure

```
frontend/
├── app/
│   ├── layout.tsx                           # Global shell (sidebar + header + book context)
│   ├── page.tsx                             # Dashboard
│   ├── (reader)/
│   │   ├── library/page.tsx                 # Book library (upload, list, manage)
│   │   ├── books/[id]/page.tsx              # Book detail + chapter list
│   │   ├── read/[bookId]/[chapter]/page.tsx # Annotated reader
│   │   └── chat/page.tsx                    # Chat RAG
│   ├── (explorer)/
│   │   ├── graph/page.tsx                   # Sigma.js graph explorer
│   │   ├── timeline/[bookId]/page.tsx       # Event + progression timeline
│   │   ├── entity/[type]/[name]/page.tsx    # Entity wiki page
│   │   └── search/page.tsx                  # Global entity search
│   └── (admin)/                             # V2
├── components/
│   ├── ui/                                  # shadcn/ui primitives
│   ├── graph/                               # SigmaGraph, GraphControls, GraphLegend
│   ├── reader/                              # AnnotatedText, ChapterNav
│   ├── timeline/                            # TimelineView, ProgressionCard
│   ├── chat/                                # ChatMessage, SourceCard, EntityMention
│   └── shared/                              # EntityBadge, BookSelector, SearchCommand
├── stores/                                  # Zustand
│   ├── book-store.ts                        # Selected book, chapters, preferences
│   ├── graph-store.ts                       # Graph state, filters, selection
│   └── ui-store.ts                          # Sidebar, theme, layout
├── hooks/
│   ├── use-book.ts, use-entity.ts
│   ├── use-graph-data.ts
│   └── use-sse.ts                           # Server-Sent Events hook
└── lib/
    ├── api/                                 # Typed API client (books.ts, graph.ts, chat.ts)
    ├── constants.ts                         # Entity colors, labels
    └── utils.ts                             # cn(), formatters
```

### 4.3 New Backend Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/stream/extraction/{book_id}` | SSE: real-time extraction progress per chapter |
| `GET` | `/api/books/{id}/chapters/{num}/text` | Chapter full text for the Reader |
| `GET` | `/api/books/{id}/chapters/{num}/entities` | Grounded entities with char offsets for annotation overlay |
| `GET` | `/api/graph/entity/{type}/{name}` | Full entity wiki page (properties + connections + timeline) |
| `GET` | `/api/graph/communities/{book_id}` | Community summaries (auto-generated clusters) |
| Updated | `/api/chat/query` | Add `max_chapter` param for spoiler-free queries |
| Updated | `/api/graph/timeline/{book_id}` | Add level_changes and skill acquisitions to timeline |

### 4.4 State Management

**Zustand** with 3 stores:
- `bookStore`: `selectedBookId`, `book`, `chapters`, `preferences` (spoiler chapter, language)
- `graphStore`: `graphData`, `filters` (labels, chapter range), `selectedNode`, `layout`
- `uiStore`: `sidebarCollapsed`, `theme`, `commandOpen`

The `selectedBookId` in `bookStore` is the global context — changing it re-scopes Graph, Chat, Reader, and Timeline.

## 5. Feature Specifications

### 5.1 Graph Explorer (Sigma.js + WebGL)

**Libraries**: `@react-sigma/core`, `graphology`, `graphology-layout-forceatlas2`

**Capabilities**:
- Render 1000+ nodes with WebGL (GPU-accelerated)
- ForceAtlas2 layout (superior to d3-force for large graphs)
- Color-coded nodes by entity type (existing 10-color palette)
- Node size proportional to degree (more connected = bigger)
- Edge coloring by relationship type
- Progressive disclosure: start with Characters only, expand to full graph

**Controls**:
- Entity type filter toggles (Characters, Skills, Events, Locations...)
- Chapter range slider (temporal filter via `valid_from_chapter`/`valid_to_chapter`)
- Search bar → highlights and zooms to matching node
- Layout selector: ForceAtlas2 / Circular / Hierarchical
- Click node → side panel with entity details
- Right-click node → "Expand neighbors" (ego graph)
- Hover node → highlight direct connections, fade others
- ⌘K → global search command palette

**Data flow**:
1. `GET /api/graph/subgraph/{book_id}?label=...&chapter=...` → `graphology.Graph`
2. Sigma.js renders from graphology data structure
3. Interactions trigger `graphStore` updates → re-render

### 5.2 Annotated Reader

**Purpose**: Read a chapter with extracted entities highlighted inline.

**Architecture**:
1. Backend serves chapter text: `GET /api/books/{id}/chapters/{num}/text`
2. Backend serves entity annotations: `GET /api/books/{id}/chapters/{num}/entities`
   - Response: `[{entity_name, entity_type, char_offset_start, char_offset_end, entity_id}]`
3. Frontend `<AnnotatedText>` component:
   - Takes raw text + annotation list
   - Builds a list of `{text, annotation?}` segments by splitting at offsets
   - Renders `<span>` with colored background per entity type
   - `onHover` → `HoverCard` with entity summary
   - `onClick` → navigate to entity wiki page or open detail dialog

**Modes**:
- **Annotated** (default): entities highlighted, hoverable, clickable
- **Clean read**: annotations hidden, pure reading experience
- **Entity focus**: only show annotations for a specific type (e.g., only Characters)

**Navigation**:
- Prev/Next chapter buttons
- Chapter selector dropdown
- Scroll position remembered per chapter (localStorage)

### 5.3 Chat RAG

**Already implemented (backend)**: vector search → rerank → graph context → LLM generate.

**Frontend improvements**:
- Conversation history (Zustand session, not persisted to DB in V1)
- Streaming responses via SSE (new endpoint)
- Source citations: expandable `<SourceCard>` per source chunk (chapter, relevance, text snippet)
- Entity mentions in answers: detected and rendered as clickable `<EntityBadge>`
- Book context: auto-scoped to selected book
- Spoiler guard: "Only search up to chapter X" slider → `max_chapter` param
- Suggested questions: after upload, suggest starter questions based on extracted entities

**Backend changes**:
- Add `max_chapter: int | None` to `ChatRequest` schema
- Filter vector search: `WHERE chap.number <= $max_chapter`
- Filter graph context: `WHERE chap.number <= $max_chapter`
- SSE streaming endpoint: `GET /api/stream/chat` → stream LLM tokens

### 5.4 Timeline & Progression

**Two views**:

**A. Book Timeline** (`/timeline/{bookId}`):
- Vertical axis: chapters (1→N)
- Per chapter: event cards with significance coloring (critical=red, major=amber, minor=slate)
- Filter by significance level (slider)
- Filter by entity involvement (character selector)
- Click event → entity detail

**B. Character Progression** (embedded in entity wiki page):
- Vertical axis: chapters where the character appears
- Per chapter: level changes, skill acquisitions, class changes, title gains, key events
- Visual: stats chart showing attribute growth over time
- Data sources: existing `GET /graph/characters/{name}` + enriched timeline

**Backend changes**:
- Enrich `GET /api/graph/timeline/{book_id}` response with `level_changes` and `skill_acquisitions`
- Add character filter param: `?character=Jake`

## 6. Design System

### 6.1 Theme

- **Mode**: Dark-first (slate-950 background), light mode optional (V2)
- **Primary**: indigo-500/600 (interactive elements, Character nodes)
- **Entity palette**: 10 colors, consistent across all views (graph, reader, badges, timeline)

| Type | Color | Hex |
|------|-------|-----|
| Character | indigo | #6366f1 |
| Skill | emerald | #10b981 |
| Class | amber | #f59e0b |
| Title | pink | #ec4899 |
| Event | red | #ef4444 |
| Location | blue | #3b82f6 |
| Item | violet | #8b5cf6 |
| Creature | orange | #f97316 |
| Faction | teal | #14b8a6 |
| Concept | slate | #64748b |

### 6.2 Typography

- **Font**: Geist Sans (body), Geist Mono (code/stats)
- **Scale**: text-xs (metadata) → text-sm (body) → text-base (content) → text-lg/xl/2xl (headings)

### 6.3 Key Components (shadcn/ui)

`Dialog`, `Sheet`, `HoverCard`, `Command` (⌘K search), `Tabs`, `Slider`, `Badge`, `ScrollArea`, `Collapsible`, `Skeleton`, `Sonner` (toasts), `DropdownMenu`, `Tooltip`, `Avatar`

### 6.4 Custom Components

| Component | Purpose |
|-----------|---------|
| `<EntityBadge>` | Colored badge with icon per entity type, clickable |
| `<BookSelector>` | Global book dropdown with status and stats |
| `<AnnotatedText>` | Text with entity-colored spans (Reader) |
| `<SigmaGraph>` | Sigma.js wrapper with React controls |
| `<TimelineView>` | Vertical timeline with chapter cards |
| `<CharacterCard>` | Mini character profile card |
| `<SourceCard>` | Chat source citation (chapter, score, snippet) |
| `<ExtractionProgress>` | SSE-driven progress bar for extraction pipeline |
| `<SpoilerGuard>` | Chapter range selector for spoiler-free mode |
| `<SearchCommand>` | ⌘K palette for global entity/page search |

### 6.5 Responsive Breakpoints

- **Desktop** (≥1280): Sidebar fixed (240px) + full content
- **Tablet** (768-1279): Sidebar collapsed (icons only, 60px) + content
- **Mobile** (<768): Sidebar as drawer (hamburger toggle) + full-width content

## 7. User Flow

### Primary Flow: "I just finished Primal Hunter Tome 1"

1. **Upload**: Drop epub in Library → ingestion (5s) → book appears as "completed"
2. **Extract**: Click "Extract" → SSE progress bar (Ch1/26... Ch2/26...) → "extracted" (~5min)
3. **Embed**: Auto-chains → "embedded" (~30s)
4. **Explore**: Open Graph Explorer → interactive universe map. Filter Characters → see relationship network. Click Jake → full profile panel
5. **Read**: Open Chapter 5 in Reader. "Œil de l'Archer" highlighted in green (Skill), "Jake" in indigo (Character), "La Grande Forêt" in blue (Location). Hover → tooltip
6. **Ask**: Open Chat → "What skills did Jake acquire?" → detailed answer with chapter citations
7. **Track**: Open Jake's Timeline → level-by-level progression, skill acquisition timeline, key events
8. **Spoiler-free**: Set spoiler guard to chapter 10 → graph, chat, and timeline only show content through chapter 10

## 8. V1 Scope

### In V1 (ship first)

- [ ] Frontend refactoring: Next.js + shadcn/ui + Zustand
- [ ] Library page (upload, list, manage books)
- [ ] Graph Explorer (Sigma.js + WebGL)
- [ ] Annotated Reader (chapter text + entity overlay)
- [ ] Chat RAG (improved UI + spoiler guard)
- [ ] Timeline (book events + character progression)
- [ ] Entity wiki pages
- [ ] Global search (⌘K)
- [ ] SSE extraction progress
- [ ] Book context selector (global)
- [ ] Responsive layout

### Out of V1 (V2+)

- [ ] Studio: ontology editor, prompt configuration, pipeline correction UI
- [ ] Admin: cost dashboard, DLQ management, monitoring
- [ ] Light mode
- [ ] Multi-language support (currently French-optimized)
- [ ] User accounts and auth (currently API key only)
- [ ] Conversation persistence (DB-backed chat history)
- [ ] Community summaries (Leiden clustering + LLM summarization)
- [ ] Visual query builder
- [ ] Comparison view (side-by-side characters/factions)
- [ ] Export (PDF wiki, JSON, CSV)

## 9. Tech Stack Summary

| Layer | Technology |
|-------|-----------|
| Framework | Next.js 16 (App Router) |
| UI Library | shadcn/ui (Radix primitives + Tailwind) |
| Graph Viz | Sigma.js (@react-sigma/core) + graphology |
| State | Zustand |
| Icons | Lucide React |
| Styling | Tailwind CSS v4 |
| API Client | Typed fetch (existing pattern, split by domain) |
| Real-time | Server-Sent Events (EventSource API) |
| Backend | FastAPI (Python 3.12, async) |
| Database | Neo4j 5.x (Cypher) |
| Embeddings | BAAI/bge-m3 (local, CUDA) |
| LLM | Gemini 2.5 Flash (extraction + chat) |
| Queue | arq + Redis |
| Monitoring | LangFuse + structlog |
