# WorldRAG UI Redesign — Design Spec

**Date**: 2026-03-15
**Scope**: Complete frontend UI overhaul — dashboard, workspace, library, navigation, upload flow
**Approach**: Incremental redesign by zone (Approach B)
**Testing**: Playwright E2E + verification agents per zone

---

## 1. Design Principles

- **Writer-first**: Every decision serves the fiction author managing sagas
- **Vault metaphor**: Projects are workspaces (like Obsidian vaults), not file folders
- **Auto-everything**: Metadata enrichment, parsing, cover extraction — no manual steps
- **Visual library**: Books are covers on shelves, not rows in a table
- **Carte blanche on style**: Professional, polished, cohesive — dark-first with warm accents

## 2. Architecture Overview

```
/                                → Dashboard (vault grid)
/projects/[slug]                 → Library (book card grid + upload)
/projects/[slug]/books/[id]      → Book detail (cover + metadata + tabs)
/projects/[slug]/graph           → Graph explorer (existing, polished)
/projects/[slug]/chat            → Chat (existing, polished)
/projects/[slug]/profile         → Ontology profile (existing)
/projects/[slug]/settings        → Project settings (simplified)
/projects/[slug]/books/[id]/extraction  → Extraction dashboard (existing)
/projects/[slug]/books/[id]/reader/[n]  → Reader (existing, polished)
```

## 3. Zone 1 — Dashboard (`/`)

### Layout
- Full-width page, no sidebar
- Header: Logo "WorldRAG" (Outfit font) left, search bar center, theme toggle + "New Project" button right
- Content: Responsive grid of vault cards (3 cols desktop, 2 tablet, 1 mobile)
- Max-width 1400px centered

### Vault Card
- **Cover mosaic**: Auto-composed from book covers in the project
  - 1 book: single cover, full card width, 200px height
  - 2-3 books: side-by-side covers
  - 4+ books: 2x2 grid of first 4 covers
  - 0 books: gradient placeholder with project initial
- **Title**: Project name, Outfit semibold, truncate at 2 lines
- **Subtitle**: "N livres · M entités · Dernière activité il y a Xh"
- **Progress bar**: thin (2px), shows extraction completion ratio
- **Context menu**: 3-dot icon top-right → Rename, Delete
- **Hover**: subtle scale(1.02) + shadow elevation, 150ms ease
- **Click**: navigates to `/projects/[slug]`

### Create Project
- "New Project" button → Dialog modal
- Fields: Name (required), Description (optional textarea)
- On submit: POST /projects → redirect to `/projects/[slug]`

### Empty State
- Centered illustration (or large icon)
- "Create your first universe" heading
- "New Project" CTA button
- Subtle animated background (optional)

## 4. Zone 2 — Workspace Layout (`/projects/[slug]/layout.tsx`)

### Sidebar (260px desktop, collapsible)
- **Header**: Back arrow (→ dashboard) + project name (Outfit, editable on double-click)
- **Section "Library"**:
  - Link to `/projects/[slug]` with BookOpen icon + "Library" label + book count badge
- **Section "Books"**:
  - Vertical list of books with:
    - Mini cover thumbnail (40x56px, rounded-sm)
    - Title (truncated, 1 line)
    - Status dot (green=done, blue=extracting, amber=pending, red=error)
  - Click → `/projects/[slug]/books/[id]`
  - Collapsible if > 6 books (show 5 + "Show N more")
- **Separator**
- **Section "Tools"**:
  - Graph (Network icon)
  - Chat (MessageCircle icon)
  - Ontology Profile (Dna icon)
- **Footer**: Settings (Gear icon) → `/projects/[slug]/settings`

### Responsive
- `>= 1280px`: Full sidebar (260px)
- `>= 768px < 1280px`: Icon-only sidebar (56px), tooltip on hover
- `< 768px`: No sidebar, hamburger in top bar opens Sheet drawer

### Top Bar (h-14, sticky)
- Left: Breadcrumb (`Project Name / Library / Book Title / ...`)
- Right: Theme toggle
- Border-bottom subtle (1px border-border)

### Main Content Area
- `flex-1`, overflow-y-auto
- Padding: p-6 desktop, p-4 mobile
- Max-width: 1200px centered (except graph page = full-bleed)

## 5. Zone 3 — Library Page (`/projects/[slug]/page.tsx`)

### Layout
- Header: "Library" title (h1, Outfit) + book count + sort dropdown (Date added, Title, Status)
- Body: Responsive grid of book cards (4 cols xl, 3 lg, 2 md, 1 sm)
- Last grid slot: Upload card (dashed border, "+" icon, "Add a book" label)

### Book Card
- **Cover image**: Full card width, aspect-[2/3], object-cover, rounded-t-lg
  - If no cover: gradient placeholder with book initial + title overlay
- **Body** (below cover):
  - Title (font-semibold, truncate 2 lines)
  - Author (text-sm text-muted-foreground)
  - Status badge (bottom-right of cover, absolute positioned)
  - Progress bar (thin, below title area) showing extraction %
- **Hover**: scale(1.02) + shadow, 150ms ease
- **Click**: → `/projects/[slug]/books/[id]`
- **Context menu** (right-click or 3-dot): Delete, Re-extract

### Upload Card (integrated in grid)
- Dashed border card, same dimensions as book cards
- Center: Upload icon + "Add a book"
- Click: opens file picker (.epub, .pdf, .txt)
- Drag-drop: entire card is a drop zone
- Also: global drag-drop on the entire page (overlay appears)

### Upload Flow
1. File dropped/selected
2. Card appears immediately with skeleton cover + pulsing animation
3. POST `/projects/[slug]/books` (FormData)
4. Backend: parse → enrich metadata (OpenLibrary) → extract cover from epub
5. Card updates live: cover appears, title/author fill in, status badge shows "Parsing"
6. Toast: "Book added successfully"
7. No page refresh needed (optimistic update + SWR revalidation)

### Empty State
- Centered: large Upload icon
- "Drop your first book here" heading
- "Supports EPUB, PDF, TXT" subtitle
- Full-page drop zone

## 6. Zone 4 — Book Detail Page (`/projects/[slug]/books/[id]`)

**New page** (currently books go directly to extraction).

### Layout (2 columns on desktop)
- **Left column** (300px fixed):
  - Cover image large (full width, aspect-[2/3], rounded-lg, shadow)
  - If no cover: styled placeholder
- **Right column** (flex-1):
  - Title (h1, Outfit)
  - Author (text-lg, muted)
  - Metadata grid (2 cols):
    - Publisher, Publication date
    - Chapters count, Word count
    - Status badge (large)
  - Description/Synopsis (from OpenLibrary or epub metadata)
  - Action buttons row:
    - "Extract entities" (primary, if not yet extracted)
    - "Open reader" (secondary)
    - "View in graph" (secondary, filtered to this book)
    - "Re-extract" (ghost, if already extracted)

### Tabs below (full width)
- **Chapters**: Ordered list, click → reader. Show extraction status per chapter
- **Entities**: Preview grid of extracted entities (grouped by type, entity badges)
- **Extraction**: Current extraction dashboard (relocated from separate page)

### Mobile
- Single column: cover on top, metadata below, tabs below

## 7. Zone 5 — Design System Updates

### Color Tokens (keep existing palette, refine)
- Keep violet primary (#6d28d9 light, #a78bfa dark)
- Keep entity color map (15 types)
- Add: `--success: emerald-500`, `--warning: amber-500`, `--info: blue-500`
- Refine card backgrounds: slightly more contrast in dark mode

### Typography
- Display headings: Outfit (semibold/bold)
- Body: DM Sans (regular/medium)
- Reader: Literata (serif, for chapter reading)
- Code/mono: JetBrains Mono

### Component Patterns
- Cards: rounded-xl, hover scale(1.02) + shadow-lg transition, 150ms ease
- Badges: rounded-full, small text, status-colored
- Buttons: rounded-lg, size variants (sm/default/lg)
- Skeleton loaders: on every async content area
- Transitions: 150ms ease for hovers, 200ms for panels

### Spacing
- Page padding: p-6 (desktop), p-4 (mobile)
- Card gaps: gap-4 (grid)
- Section spacing: space-y-8

## 8. Zone 6 — Polish Existing Pages

### Graph Explorer
- Keep Sigma.js + graphology + ForceAtlas2
- Improve: node detail panel styling (card with cover-like header)
- Add: smooth transition when panel opens/closes
- Keep: filters, search, stats bar

### Chat
- Keep: thread sidebar, streaming, citations, feedback
- Improve: message bubble styling, better empty state
- Add: smoother scroll-to-bottom animation

### Reader
- Keep: XHTML renderer + chapter navigation
- Improve: Literata font larger (18px base), better line-height (1.8)
- Add: reading progress indicator in top bar

### Settings
- Simplify: single card with project name/description edit
- Danger zone: delete project (with confirmation)

## 9. Testing Strategy

### Playwright E2E Tests
- **Dashboard**: Create project, verify card appears, rename, delete
- **Library**: Upload epub (use `tests/fixtures/primal-hunter.epub`), verify card appears with metadata
- **Book Detail**: Navigate to book, verify metadata displayed, tabs work
- **Navigation**: Sidebar links work, breadcrumbs correct, responsive collapse
- **Upload Flow**: Drag-drop works, file picker works, progress feedback shown

### Test Infrastructure
- Playwright config targeting frontend on port 49516
- Backend must be running on port 49515
- Test fixtures: `tests/fixtures/primal-hunter.epub`
- Verification agents review each zone after implementation

## 10. Implementation Zones (for parallel agents)

| Zone | Scope | Dependencies |
|------|-------|-------------|
| Z1 - Dashboard | New page layout, vault cards, create dialog | None |
| Z2 - Workspace Layout | Sidebar redesign, top bar, responsive | None |
| Z3 - Library | Book card grid, upload integration, empty state | Z2 (layout) |
| Z4 - Book Detail | New page, cover+metadata layout, tabs | Z2 (layout) |
| Z5 - Design System | Token refinements, component patterns | None (parallel) |
| Z6 - Polish | Graph, Chat, Reader, Settings improvements | Z2 (layout) |
| Z7 - Playwright Tests | E2E test suite for all zones | All zones |

Z1, Z2, Z5 can run in parallel. Z3, Z4 depend on Z2. Z6 depends on Z2. Z7 runs after all.
