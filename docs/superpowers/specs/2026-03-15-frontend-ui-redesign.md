# WorldRAG Frontend UI Redesign — Complete Spec

**Date**: 2026-03-15
**Author**: Nicolas + Claude
**Status**: Approved

---

## 1. Overview

Complete frontend redesign replacing the current tab-based project UI with a sidebar-driven, two-level navigation architecture. The redesign restores all features lost in the v2 migration (reader, extraction monitoring, graph filters, chat spoiler guard) and introduces a modern flat design system.

### Goals

1. Working pipeline: upload → parse → read → extract → explore → chat
2. Sidebar contextual navigation (project-level + book-level)
3. Responsive layout (desktop labels, tablet icons, mobile drawer)
4. Flat modern design — original, anti-AI-slop, typography-driven
5. Real-time feedback throughout (SSE for parsing + extraction progress)

### Non-Goals

- Entity CRUD / merge-split tool (v1.1)
- Wiki auto-generation (v1.1)
- Reader KG annotations (architecture ready, implementation later)
- Multi-user / collaboration
- Editable SagaProfile

---

## 2. Design System

### Typography

- **Primary font**: System sans-serif (`font-sans`) for all UI chrome
- **Reader font**: System serif (Georgia) for book text content only
- **Data font**: `font-mono` for counters, stats, logs, code, regex patterns
- Typography is the primary structuring element — hierarchy via weight/size, not color or borders

### Color Philosophy

Colors encode meaning only. No decorative color.

**Statuses**:

| Status | Color | Token |
|---|---|---|
| parsing | `blue-500` | Processing |
| ready | `slate-500` | Awaiting action |
| extracting | `amber-500` | Active work (pulse animation) |
| done | `emerald-500` | Complete |
| error | `red-500` | Failed |

**Entity type palette** (consistent across entire app):

| Type | Color |
|---|---|
| Character | `blue-500` |
| Skill | `violet-500` |
| Class | `amber-500` |
| Event | `rose-500` |
| Location | `emerald-500` |
| Item | `orange-500` |
| System | `cyan-500` |
| Title | `fuchsia-500` |
| Level | `lime-500` |
| Faction | `teal-500` |
| Arc | `slate-400` |

### Surfaces & Borders

- Opaque surfaces only — white (`bg-background`) / gray-950 dark mode
- No backdrop blur, no glass morphism, no gradients
- Borders: 1px `border-gray-200` / `border-gray-800`, used minimally and intentionally
- `shadow-sm` on floating panels only (graph overlays, dropdowns)

### Spacing & Layout

- Generous whitespace — space is a design element
- Content areas use consistent padding (`p-6` pages, `p-4` panels)
- Tables use `py-2 px-3` cell padding

### Animations

- Functional only: sidebar transitions, panel slide-ins, content fade-in
- No decorative animations, no gradient mesh, no floating blobs
- `tabular-nums` on all numeric counters to prevent layout shift
- Extraction status `extracting`: subtle pulse on the status dot only

### Responsive Breakpoints

| Breakpoint | Sidebar | Behavior |
|---|---|---|
| ≥1280px | Fixed 220px, labels visible | Full layout |
| 768–1279px | Collapsed 56px, icon-only, expand on hover | Compact |
| <768px | Hidden, drawer overlay via hamburger | Mobile |

---

## 3. Navigation Architecture

### Sidebar — Two Levels

Replaces the current tab-based navigation entirely.

**Level 1 — Project** (top section, fixed):

```
Graph        → /projects/[slug]/graph
Chat         → /projects/[slug]/chat
Profile      → /projects/[slug]/profile
Settings     → /projects/[slug]/settings
```

**Level 2 — Books** (bottom section, scrollable):

```
Books header → /projects/[slug]  (books table)
├ Book 1 (accordion, expandable)
│  ├ Chapters  → /projects/[slug]/books/[bookId]/chapters
│  ├ Reader    → /projects/[slug]/books/[bookId]/reader
│  └ Extraction → /projects/[slug]/books/[bookId]/extraction
├ Book 2
│  ├ Chapters
│  ├ Reader
│  └ Extraction
└ [+ Add book]  (triggers file picker or drop zone)
```

Each book shows a status badge inline: `○ parsing`, `◐ ready`, `◌ extracting`, `● done`, `✕ error`.

Book accordion: collapsed by default. Clicking a book name expands it to show sub-navigation. Clicking a sub-item navigates to that view.

### TopBar (48px)

- **Left**: Project name (link → `/projects` dashboard), breadcrumb separator `›`, contextual path (e.g., `Book 1 › Reader › Ch.3`)
- **Right**: Theme toggle (sun/moon), back to projects link
- Minimal, single row, `border-b` only

### Route Structure

```
/projects                              → Dashboard (project grid)
/projects/[slug]                       → Books table (landing)
/projects/[slug]/graph                 → Graph explorer
/projects/[slug]/chat                  → Chat interface
/projects/[slug]/profile               → Ontology profile
/projects/[slug]/settings              → Project settings
/projects/[slug]/books/[bookId]/chapters   → Chapter list
/projects/[slug]/books/[bookId]/reader     → Book reader
/projects/[slug]/books/[bookId]/reader/[chapterId] → Reader at chapter
/projects/[slug]/books/[bookId]/extraction → Extraction dashboard
```

---

## 4. Books Table & Upload Flow

### Books Table View (`/projects/[slug]`)

Landing page of a project. Clean table, no cards.

**Columns**: `#` (book number), `Title`, `Chapters` (count or `—`), `Words` (formatted with thousands separator or `—`), `Status` (badge)

**Row interactions**:
- Click → expands the book in the sidebar and navigates to Chapters view
- Hover → shows `⋯` menu icon on the right
- Menu actions: Delete (with confirmation), Re-extract, Download original

**Drop zone**: Always visible below the table. Dashed border `border-gray-300`, text `text-muted`. Drag-over: `border-blue-500`, `bg-blue-50` (5% opacity).

Also: `[+ Upload]` button in the page header as alternative to drag-and-drop.

### Upload Flow

```
File dropped or selected
  → POST /projects/{slug}/books (multipart upload)
  → Row appears immediately in table with status "○ parsing"
  → Backend: ingest_file() parses chapters + creates chunks
  → SSE or polling: chapter count updates in real-time on the row
  → Parsing complete → status changes to "◐ ready"
  → User navigates to Extraction tab → clicks "Start extraction"
  → Status → "◌ extracting"
  → Extraction complete → status → "● done"
```

No redirect on upload. Non-blocking — user can upload multiple files sequentially.

### Empty State

No empty table with headers. Dedicated empty state:

```
Upload your first book

Drop an EPUB, PDF, or TXT file here
to start building your knowledge graph

[ Browse files ]
```

Centered text, large typography, single CTA. No illustration, no hero icon.

---

## 5. Chapter List (`/projects/[slug]/books/[bookId]/chapters`)

Simple table view of all chapters in a book.

**Columns**: `#`, `Title`, `Words` (formatted), `Status` (parsing status of individual chapter)

This is a reference/overview. Clicking a chapter row navigates to the Reader at that chapter.

---

## 6. Reader (`/projects/[slug]/books/[bookId]/reader`)

### Layout

Reader takes the full content area. No additional side panels — the project sidebar already provides the table of contents (chapter list under the book accordion).

### Text Rendering

- **Column**: centered, `max-w-[680px]` — optimal reading width (~65-75 chars/line)
- **Font**: serif (Georgia / system serif) for body text
- **Size**: `text-lg` (18px), `leading-relaxed` (1.625 line-height)
- **Paragraph spacing**: `space-y-6`
- **Chapter header**: chapter number in `text-sm text-muted` above, title in `text-2xl font-semibold` sans-serif

### Navigation

- **Sidebar**: the book's chapter list in the sidebar IS the table of contents. Active chapter marked with `►` and `font-semibold`.
- **Footer**: prev/next buttons at the bottom of the text. Shows adjacent chapter titles. `text-sm text-muted`, hover → `text-foreground`.
- **Progress**: chapter number / total + thin progress bar at the bottom. Not sticky — lives at end of content.

### Scroll Behavior

Natural scroll. No artificial pagination, no simulated "pages". The chapter text loads and scrolls naturally.

### Annotation Architecture (for future use)

```tsx
// Today: pure text rendering
<ChapterContent text={chapter.text} annotations={[]} />

// Future: KG entity highlights
<ChapterContent
  text={chapter.text}
  annotations={entities.map(e => ({
    start: e.char_start,
    end: e.char_end,
    type: e.label,
    entityId: e.id
  }))}
/>
```

Annotations split the text into spans. Without annotations → zero overhead, plain text. With annotations → clickable spans colored by entity type.

### States

- **Chapter loading**: skeleton loader (3-4 `bg-muted` animated lines)
- **Book still parsing**: "This book is still being parsed" + progress indicator
- **Parse error**: inline error message with retry button

---

## 7. Extraction Dashboard (`/projects/[slug]/books/[bookId]/extraction`)

### Layout — Three Vertical Zones

1. Header with 4 stat counters + donut chart
2. Chapter table (expandable rows)
3. Live feed (during extraction)

### Header — 4 Counters

Four blocks in a row. Number in `text-3xl font-mono font-semibold`, label below in `text-xs text-muted uppercase tracking-wide`.

| Counter | Content |
|---|---|
| Entities | Total cumulative, increments in real-time |
| Relations | Total cumulative, increments in real-time |
| Chapters | `done/total` with thin progress bar below |
| Cost | Cumulative API cost in dollars |

All numbers use `tabular-nums` CSS to prevent dancing.

### Entity Breakdown — Donut Chart

Positioned to the right of the chapter table header area.

- Each segment = one entity type, colored per entity palette
- Legend below: color dot + label + count
- Updates in real-time during extraction
- Empty state: gray donut with "No entities yet" centered

### Chapter Table

**Columns**: `#`, `Chapter` (title), `Words` (formatted), `Entities` (count or `—`), `Status`

**Status badges**:
- `○ pending` — gray
- `◌ extracting` — amber, pulse animation
- `● done` — emerald
- `✕ error` — red, tooltip with error message

**Expandable rows (accordion)**: Click a `done` row to expand and show:
- Breakdown by entity type: `Characters: 5, Skills: 3, Classes: 2, Events: 4, Locations: 3, Items: 2, Systems: 1`
- `Relations: 12`
- `[Retry]` button visible only on error rows

**Scroll**: Table scrolls independently if many chapters. Sticky header.

### Live Feed

- **Position**: bottom of the page, fixed height `200px`, auto-scrolls to bottom
- **Auto-scroll**: active as long as user hasn't manually scrolled up. If user scrolls up, auto-scroll pauses. Scroll back to bottom resumes it.
- **Line format**: `HH:MM:SS  Ch.N → Type: EntityName` in `font-mono text-sm`
- **Color**: entity type name colored per palette, rest in `text-muted`
- **Completion**: final line "Extraction complete — {n} entities, {n} relations" in `text-foreground font-medium`
- **Hidden when idle**: when no extraction is running, feed is hidden, table takes full height. Expandable via "Show extraction log" link if a past extraction exists.

### Action Button (top-right)

| Book state | Button | Style |
|---|---|---|
| `ready` (never extracted) | `Start extraction` | Primary |
| `ready` (Book 1 in project) | `Start discovery extraction` | Primary, with `?` tooltip explaining discovery vs guided |
| `ready` (Book 2+) | `Start guided extraction` | Primary, with `?` tooltip |
| `extracting` | `Cancel` | Destructive outline |
| `done` | `Re-extract` | Secondary outline |
| `error` (partial) | `Resume` | Primary (resumes failed chapters only) |

### States

- **Before parsing**: "Book is being parsed, extraction will be available once chapters are ready" + spinner
- **Ready, never extracted**: chapter table visible (titles + word counts), entity columns empty, feed hidden, action button active
- **Extracting**: everything live — counters, table updating, feed scrolling, "Cancel" button
- **Done**: final counters, complete table, feed hidden (expandable), "Re-extract" button
- **Partial error**: done chapters in green, error chapters in red with per-chapter retry, "Resume" global button

---

## 8. Graph Explorer (`/projects/[slug]/graph`)

### Layout

Full-bleed. The Sigma.js canvas fills the entire content area. All controls float above it.

### Canvas

- `position: absolute; inset: 0` within the content area
- Background: `gray-50` (light) / `gray-950` (dark) — slightly different from sidebar for depth without borders
- **Nodes**: circles, size proportional to degree. Color per entity type palette.
- **Labels**: entity name, `font-mono text-xs`. Visible only above a zoom threshold to avoid text soup. On hover → label always visible.
- **Edges**: `gray-300` / `gray-700`, 1px. On node hover → connected edges take source type color, all others fade to `opacity: 0.1`.
- **Layout**: ForceAtlas2, stabilizes after a few seconds then freezes.

### Floating Panels

All panels: `position: absolute`, opaque background, `border` 1px, `shadow-sm`. No blur, no glass.

**1. Search (top-left)**
- Text input with search icon
- Dropdown results on keystroke (debounce 200ms)
- Each result: color dot for type + name + type label in `text-muted`
- Select → graph zooms to node, node pulses once, detail panel opens
- `Escape` closes dropdown

**2. Book Selector (top-right)**
- Simple dropdown: list of extracted books
- Change → reload subgraph with fade transition
- Hidden if only one book

**3. Filters (left, below search)**
- **Entity type toggles**: checkbox + color dot + label + count per type. Uncheck → hides nodes of that type + orphaned edges.
- **Chapter range slider**: dual-handle slider `min–max` filtering entities by `valid_from_chapter`. Label: "Ch. {min} — {max}". Also serves as spoiler control.
- Panel is collapsible via chevron
- Filters apply in real-time, no "Apply" button

**4. Node Detail (right, slide-in)**
- Appears on node click, slides from right (`translate-x` transition)
- **Header**: entity name `text-xl font-semibold` + colored type badge
- **Metadata**: first appearance (chapter), last mention, relation count
- **Relations**: grouped by relation type. Each group: relation label + count, expandable to show targets. Click target → navigate to that node in graph.
- **Description**: entity summary from KG if available, `text-sm`
- **Actions**:
  - `[Open in Reader]` → navigates to Reader at first appearance chapter
  - `[View in Chat]` → opens Chat with pre-filled query about this entity
- **Close**: `✕` button or click on canvas

**5. Stats + Zoom (bottom-center)**
- Compact bar: `{n} nodes · {n} edges` in `font-mono text-sm text-muted`
- Zoom buttons: `[−]` `[⊞ fit]` `[+]`
- Single row, opaque background

### Interactions

| Action | Result |
|---|---|
| Hover node | Slight enlarge, show label, highlight neighbors, dim rest |
| Click node | Open detail panel, center view on node |
| Hover edge | Tooltip with relation type |
| Drag node | Move node, edges follow, layout doesn't recalculate (node pinned) |
| Scroll | Zoom centered on cursor |
| Drag canvas | Pan |
| Double-click canvas | Close detail panel |

### States

- **No extracted book**: empty canvas, centered message "Extract a book to explore its knowledge graph" + link to Books
- **Loading**: neutral background + centered spinner
- **Empty after filter**: "No entities match your filters" centered
- **>2000 nodes**: warning in filter panel "Showing top 2000 nodes by degree. Narrow filters for full view."

---

## 9. Chat (`/projects/[slug]/chat`)

### Layout

Two columns: thread sidebar (180px) on the left, conversation area on the right.

### Thread Sidebar (180px)

- **Header**: `+ New` button to create a new thread
- **Grouping**: by day — "Today", "Yesterday", "Mar 12". Labels in `text-xs text-muted uppercase`
- **Thread item**: truncated title (first user query), single line, `text-sm`. Active thread: `font-medium bg-muted/50`. Hover: `bg-muted/30`.
- **Delete**: `✕` icon on hover. Click → inline confirmation: title replaced by "Delete? Yes / No"
- **Scroll**: independent scroll. Max 50 threads, oldest drop off.
- **Responsive**: on screens < 1280px, thread sidebar hides behind a toggle icon at the top of the chat area.

### Chat Header

Single compact line below the page title:

- **Book selector**: dropdown of extracted books. Changes retrieval context.
- **Spoiler guard**: dropdown `Ch.1–{max}`. Limits retrieval to chapters in this range.
  - Default: full book
  - Format: "Spoiler: Ch.1–32"
  - When limit < max: amber badge as visual reminder

### Messages

**User message**:
- Right-aligned, `bg-muted` background, `rounded-lg`, `text-sm`
- `max-w-[75%]`

**Assistant message**:
- Left-aligned, no background (text on page background), `text-sm`
- `max-w-[75%]`
- **Confidence badge**: inline right of "Assistant" label. `text-xs font-mono`:
  - `● High` — emerald, score ≥ 0.8
  - `◐ Medium` — amber, score 0.5–0.8
  - `○ Low` — red, score < 0.5
- **Inline citations**: `[Ch.X, §Y]` rendered as clickable links `text-blue-500 underline`. Click → navigates to Reader at that chapter and scrolls to the paragraph.
- **Sources**: collapsible block below message, closed by default. `▾ Sources` chevron to open. Each source: `border rounded` block, `font-mono text-xs`, chapter + section ref + truncated excerpt (50 chars). Click → opens in Reader.
- **Feedback**: `👍 👎` bottom-right of message, `text-muted`, appear on hover. Click → selected icon becomes `text-foreground`, other disappears. POST to backend.
- **Streaming**: tokens appear incrementally. Blinking `|` cursor at end during stream. Sources appear all at once when stream completes.

**System message** (errors, info):
- Centered, `text-xs text-muted italic`, no bubble

### Input

- **Position**: sticky bottom, full chat width
- **Style**: `border-t` only, no floating box. `text-sm` input, placeholder "Ask about this book..."
- **Send button**: `→` icon, `text-muted` when empty, `text-foreground` when content exists
- **During streaming**: send button transforms to `■ Stop`. Click → abort stream.
- **Shortcuts**: `Enter` to send, `Shift+Enter` for newline
- **Multiline**: textarea grows up to 4 lines max, then internal scroll

### States

- **No extracted book**: chat area disabled, centered "Extract a book to start chatting about it"
- **New thread, no messages**: subtle welcome message centered vertically:
  ```
  Ask anything about {book title}.
  Try: "Who are the main characters?" or "Explain the magic system"
  ```
  `text-muted text-sm`. Disappears on first message.
- **Stream error**: system message "Something went wrong. Try again." with `[Retry]` link
- **Rate limit**: system message "Too many requests, please wait a moment." with countdown timer

---

## 10. Profile (`/projects/[slug]/profile`)

### Layout

Single scrollable page with three sections.

### Header

- Title: "Ontology Profile — {project name}"
- Subtitle: "Induced from {book title} · {n} types · {n} relations · {n} patterns"
- Read-only for now. No edit actions.

### Section 1 — Entity Types

Horizontal bar chart. One bar per entity type.

- Bar width proportional to confidence score (%)
- Bar color from entity type palette
- Right of bar: `{confidence}%  ({count})` in `font-mono text-sm`
- Sorted by confidence descending
- Hover: tooltip with induced description of the type

### Section 2 — Relation Types

Simple table:

| Column | Content |
|---|---|
| Relation | Relation name (e.g., `HAS_SKILL`) |
| From → To | Entity types (e.g., `Character → Skill`) |
| Temporal | `yes` badge (amber) or `no` (muted) |

Hover on row: tooltip with description and example.

### Section 3 — Text Patterns

Accordion list. Each pattern:

- **Collapsed**: pattern name only
- **Expanded**:
  - Regex: `font-mono bg-muted px-2 py-1 rounded`
  - Extracts: entity type badges (colored)
  - Example: `italic text-muted`
- Sorted by frequency of use descending

### Empty State

```
No ontology profile yet.
Upload and extract your first book to discover the universe's structure.
```

---

## 11. Settings (`/projects/[slug]/settings`)

### Fields

- **Project name**: text input, editable
- **Description**: textarea, 2 lines, optional
- **Slug**: `font-mono text-muted`, read-only (generated at creation)
- **Created**: date, read-only

### Actions

- **Save changes**: primary button, disabled until a field changes. Inline "Saved" feedback that disappears after 2s.
- **Danger zone**: separated by `border-t`. "Delete this project and all its data. This action cannot be undone." + red outline button `[Delete project]`. Click → confirmation dialog: "Type the project name to confirm deletion" with input. Exact match required to enable "Delete permanently" button.

---

## 12. Dashboard (`/projects`)

### Layout

Grid of project cards. Existing implementation is mostly fine — keep the grid layout, remove the glass morphism.

### Project Card

Clean card with `border`, no shadow, no blur:

- **Title**: `text-lg font-semibold`
- **Description**: `text-sm text-muted`, 2 lines max truncated
- **Stats row**: `{n} books · {n} entities` in `text-xs text-muted font-mono`
- **Last updated**: relative time `text-xs text-muted`
- Click → navigate to `/projects/[slug]`

### Create Project

`[+ New project]` button top-right. Opens dialog:
- Project name input (required)
- Description textarea (optional)
- Slug auto-generated from name, shown as preview in `font-mono text-sm text-muted`
- `[Create]` button

### Empty State

```
No projects yet.
Create your first project to start building knowledge graphs from your books.

[ Create project ]
```

---

## 13. Component Architecture

### New Components to Create

```
components/
├── layout/
│   ├── app-sidebar.tsx          # Two-level sidebar (project + books)
│   ├── sidebar-project-nav.tsx  # Level 1: Graph, Chat, Profile, Settings
│   ├── sidebar-book-list.tsx    # Level 2: book accordion with sub-nav
│   ├── sidebar-book-item.tsx    # Single book accordion item
│   ├── top-bar.tsx              # Breadcrumb + theme toggle (rewrite)
│   └── mobile-drawer.tsx        # Mobile sidebar overlay
│
├── books/
│   ├── books-table.tsx          # Main books table
│   ├── book-row.tsx             # Single table row with status + actions
│   ├── book-status-badge.tsx    # Status indicator (parsing/ready/extracting/done/error)
│   ├── upload-drop-zone.tsx     # Drag-and-drop upload area
│   └── empty-books.tsx          # Empty state for first upload
│
├── reader/
│   ├── chapter-content.tsx      # Text renderer (accepts annotations array)
│   ├── reader-nav.tsx           # Prev/next footer navigation
│   └── reader-progress.tsx      # Chapter progress bar
│
├── extraction/
│   ├── extraction-header.tsx    # 4 stat counters
│   ├── extraction-donut.tsx     # Entity type donut chart
│   ├── chapter-table.tsx        # Expandable chapter rows
│   ├── chapter-row.tsx          # Single chapter with accordion detail
│   ├── entity-breakdown.tsx     # Type breakdown inside expanded row
│   ├── live-feed.tsx            # Real-time entity discovery log
│   └── extraction-action.tsx    # Context-aware action button
│
├── graph/
│   ├── sigma-graph.tsx          # Sigma.js canvas (rewrite for full-bleed)
│   ├── graph-search.tsx         # Search panel with autocomplete
│   ├── graph-filters.tsx        # Type toggles + chapter slider
│   ├── graph-book-selector.tsx  # Book dropdown
│   ├── node-detail-panel.tsx    # Slide-in entity detail (rewrite)
│   └── graph-stats-bar.tsx      # Bottom stats + zoom controls
│
├── chat/
│   ├── chat-message.tsx         # Message bubble (keep, adapt)
│   ├── thread-sidebar.tsx       # Thread list (keep, adapt)
│   ├── chat-header.tsx          # Book selector + spoiler guard
│   ├── chat-input.tsx           # Sticky input with send/stop
│   ├── source-panel.tsx         # Collapsible sources (keep, adapt)
│   ├── citation-highlight.tsx   # Inline citation links (keep)
│   ├── confidence-badge.tsx     # Score badge (keep)
│   └── feedback-buttons.tsx     # Thumbs up/down (keep)
│
├── profile/
│   ├── entity-type-bars.tsx     # Horizontal bar chart
│   ├── relation-type-table.tsx  # Relation types table
│   └── text-pattern-list.tsx    # Accordion pattern list
│
├── settings/
│   ├── project-settings-form.tsx  # Edit form
│   └── delete-project-dialog.tsx  # Confirmation dialog
│
├── projects/
│   ├── project-card.tsx         # Dashboard card (rewrite, remove glass)
│   └── create-project-dialog.tsx # Create dialog (keep, adapt)
│
└── shared/
    ├── entity-badge.tsx         # Entity type colored badge (keep)
    ├── status-badge.tsx         # Generic status badge
    ├── empty-state.tsx          # Reusable empty state component
    └── theme-toggle.tsx         # Sun/moon toggle (keep)
```

### Components to Delete

- `components/shared/gradient-mesh.tsx` — decorative, removed
- `components/shared/sidebar.tsx` — replaced by `layout/app-sidebar.tsx`
- `components/shared/top-bar.tsx` — replaced by `layout/top-bar.tsx`
- `components/projects/book-selector.tsx` — replaced by sidebar book list

### Stores (Zustand)

**Existing** (keep, adapt):
- `project-store.ts` — add `currentBook` state
- `chat-store.ts` — add `spoilerMaxChapter` field
- `graph-store.ts` — add `filters.entityTypes: Set<string>`, `filters.chapterRange: [min, max]`
- `ui-store.ts` — add `sidebarExpanded`, `sidebarBookAccordion: Record<string, boolean>`

**New**:
- `extraction-store.ts` — `extractionStatus`, `entityCounts`, `chapterStatuses`, `feedMessages[]`
- `reader-store.ts` — `currentChapterId`, `scrollPosition`

### Hooks

**Existing** (keep, adapt):
- `use-chat-stream.ts` — adapt for book selector + spoiler guard params

**New**:
- `use-extraction-stream.ts` — SSE hook for extraction progress (chapter status, entity counts, feed)
- `use-parsing-status.ts` — polling/SSE for book parsing progress (chapter count updates)

---

## 14. API Requirements

### Existing Endpoints (verified working)

- `POST /projects/{slug}/books` — upload
- `POST /projects/{slug}/extract` — start extraction
- `GET /projects/{slug}/graph/subgraph` — graph data
- `GET /projects/{slug}/graph/search` — entity search
- `POST /projects/{slug}/chat/stream` — chat SSE
- `POST /projects/{slug}/chat/feedback` — feedback

### Endpoints Needing Backend Work

| Endpoint | Need | Priority |
|---|---|---|
| `POST /projects/{slug}/books` | Must call `ingest_file()` to parse chapters after upload | CRITICAL |
| `GET /projects/{slug}/books/{bookId}/chapters` | Return chapter list with word counts | CRITICAL |
| `GET /projects/{slug}/books/{bookId}/chapters/{chapterId}` | Return chapter text content for reader | CRITICAL |
| `GET /projects/{slug}/books/{bookId}/extraction/stream` | SSE endpoint for extraction progress | CRITICAL |
| `GET /projects/{slug}/books/{bookId}/parsing/status` | Polling endpoint for parsing progress | HIGH |
| `DELETE /projects/{slug}/books/{bookId}` | Delete book + cascade | HIGH |
| `PUT /projects/{slug}` | Update project name/description | MEDIUM |
| `DELETE /projects/{slug}` | Delete project + full cascade | MEDIUM |
| `POST /projects/{slug}/books/{bookId}/extract/cancel` | Cancel running extraction | MEDIUM |
| `POST /projects/{slug}/books/{bookId}/extract/resume` | Resume failed chapters | MEDIUM |

---

## 15. Migration Plan

This is a big-bang layout rewrite. The approach:

1. Build the new shell (sidebar + topbar + layout) first
2. Move existing pages into the new shell
3. Build new pages (reader, extraction dashboard, chapters)
4. Enhance existing pages (graph full-bleed, chat spoiler guard)
5. Delete old components
6. Remove glass morphism / gradient mesh throughout

Every step should result in a working (if incomplete) app. No broken intermediate states.
