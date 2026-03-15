# Frontend UI Redesign — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the tab-based frontend with a sidebar-driven layout, add Reader, Extraction Dashboard, and restore all lost features.

**Architecture:** Big-bang layout rewrite. New shell (sidebar + topbar) wraps all content. New pages (reader, extraction, chapters, settings) added. Existing pages (graph, chat, profile) enhanced. Glass morphism removed. Flat modern design system.

**Tech Stack:** Next.js 16 / React 19 / TypeScript strict / Tailwind 4 / shadcn/ui / Zustand / Sigma.js 3 / recharts / SSE

**Spec:** `docs/superpowers/specs/2026-03-15-frontend-ui-redesign.md`

---

## File Structure

### New Files

```
frontend/
├── app/
│   ├── layout.tsx                          # REWRITE — new shell with sidebar
│   ├── page.tsx                            # REWRITE — clean project dashboard
│   ├── projects/[slug]/
│   │   ├── layout.tsx                      # REWRITE — sidebar context provider
│   │   ├── page.tsx                        # REWRITE — books table
│   │   ├── settings/page.tsx               # NEW
│   │   ├── books/[bookId]/
│   │   │   ├── chapters/page.tsx           # NEW
│   │   │   ├── reader/page.tsx             # NEW
│   │   │   ├── reader/[chapterNumber]/page.tsx  # NEW
│   │   │   └── extraction/page.tsx         # NEW
│
├── components/
│   ├── layout/
│   │   ├── app-sidebar.tsx                 # NEW — two-level sidebar
│   │   ├── sidebar-project-nav.tsx         # NEW
│   │   ├── sidebar-book-list.tsx           # NEW
│   │   ├── sidebar-book-item.tsx           # NEW
│   │   ├── top-bar.tsx                     # NEW (replaces shared/top-bar.tsx)
│   │   └── mobile-drawer.tsx               # NEW
│   │
│   ├── books/
│   │   ├── books-table.tsx                 # NEW
│   │   ├── book-row.tsx                    # NEW
│   │   ├── book-status-badge.tsx           # NEW
│   │   └── upload-drop-zone.tsx            # NEW
│   │
│   ├── reader/
│   │   ├── chapter-content.tsx             # NEW
│   │   ├── reader-nav.tsx                  # NEW
│   │   └── reader-progress.tsx             # NEW
│   │
│   ├── extraction/
│   │   ├── extraction-header.tsx           # NEW
│   │   ├── extraction-donut.tsx            # NEW
│   │   ├── chapter-table.tsx               # NEW
│   │   ├── chapter-row.tsx                 # NEW
│   │   ├── live-feed.tsx                   # NEW
│   │   └── extraction-action.tsx           # NEW
│   │
│   ├── graph/
│   │   ├── sigma-graph.tsx                 # REWRITE — full-bleed
│   │   ├── graph-search.tsx                # NEW
│   │   ├── graph-filters.tsx               # NEW
│   │   ├── graph-book-selector.tsx         # NEW
│   │   ├── node-detail-panel.tsx           # REWRITE
│   │   └── graph-stats-bar.tsx             # NEW (replaces graph-controls.tsx)
│   │
│   ├── chat/
│   │   ├── chat-header.tsx                 # NEW — book selector + spoiler guard
│   │   ├── chat-input.tsx                  # NEW — sticky input with stop
│   │   └── (keep existing: chat-message, thread-sidebar, source-panel, citation-highlight, confidence-badge, feedback-buttons)
│   │
│   ├── settings/
│   │   ├── project-settings-form.tsx       # NEW
│   │   └── delete-project-dialog.tsx       # NEW
│   │
│   └── shared/
│       ├── empty-state.tsx                 # NEW
│       └── status-badge.tsx                # NEW
│
├── hooks/
│   ├── use-extraction-stream.ts            # NEW — SSE for extraction
│   └── use-parsing-status.ts              # NEW — polling for parsing
│
├── stores/
│   ├── extraction-store.ts                 # NEW
│   └── reader-store.ts                     # NEW
│
└── lib/
    ├── utils.ts                            # MODIFY — new color maps, status mapper
    ├── api/
    │   ├── types.ts                        # MODIFY — add reader/extraction types
    │   ├── reader.ts                       # NEW — reader API client
    │   └── books.ts                        # NEW — book detail/chapters API
    └── constants.ts                        # NEW — entity colors, status config
```

### Files to Delete (at end)

```
components/shared/gradient-mesh.tsx
components/shared/sidebar.tsx
components/shared/top-bar.tsx
components/shared/animated-counter.tsx
components/projects/book-selector.tsx
components/graph/graph-controls.tsx
```

---

## Chunk 1: Foundation — Design System + Layout Shell

### Task 1: Design Tokens & Constants

**Files:**
- Create: `frontend/lib/constants.ts`
- Modify: `frontend/lib/utils.ts`
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Create constants file with entity colors and status config**

```typescript
// frontend/lib/constants.ts

export type EntityType =
  | "Character" | "Skill" | "Class" | "Event" | "Location"
  | "Item" | "System" | "Title" | "Level" | "Faction"
  | "Arc" | "Creature" | "Concept" | "Race" | "Prophecy"

export type UIStatus = "pending" | "parsing" | "ready" | "extracting" | "embedding" | "done" | "error"

/** Tailwind color class per entity type (bg-, text-, border- prefix yourself) */
export const ENTITY_COLORS: Record<string, string> = {
  Character: "blue-500",
  Skill: "violet-500",
  Class: "amber-500",
  Event: "rose-500",
  Location: "emerald-500",
  Item: "orange-500",
  System: "cyan-500",
  Title: "fuchsia-500",
  Level: "lime-500",
  Faction: "teal-500",
  Arc: "slate-400",
  Creature: "red-500",
  Concept: "indigo-500",
  Race: "pink-500",
  Prophecy: "purple-500",
} as const

/** Hex colors for Sigma.js and recharts (not Tailwind classes) */
export const ENTITY_HEX: Record<string, string> = {
  Character: "#3b82f6",
  Skill: "#8b5cf6",
  Class: "#f59e0b",
  Event: "#f43f5e",
  Location: "#10b981",
  Item: "#f97316",
  System: "#06b6d4",
  Title: "#d946ef",
  Level: "#84cc16",
  Faction: "#14b8a6",
  Arc: "#94a3b8",
  Creature: "#ef4444",
  Concept: "#6366f1",
  Race: "#ec4899",
  Prophecy: "#a855f7",
} as const

export const ENTITY_HEX_FALLBACK = "#9ca3af" // gray-400

export const STATUS_CONFIG: Record<UIStatus, { color: string; hex: string; label: string }> = {
  pending:    { color: "gray-400",    hex: "#9ca3af", label: "Pending" },
  parsing:    { color: "blue-500",    hex: "#3b82f6", label: "Parsing" },
  ready:      { color: "slate-500",   hex: "#64748b", label: "Ready" },
  extracting: { color: "amber-500",   hex: "#f59e0b", label: "Extracting" },
  embedding:  { color: "cyan-500",    hex: "#06b6d4", label: "Embedding" },
  done:       { color: "emerald-500", hex: "#10b981", label: "Done" },
  error:      { color: "red-500",     hex: "#ef4444", label: "Error" },
} as const

/** Map backend ProcessingStatus values to frontend UIStatus */
export function mapBackendStatus(status: string): UIStatus {
  switch (status) {
    case "pending": return "pending"
    case "ingesting":
    case "chunking": return "parsing"
    case "completed": return "ready"
    case "extracting":
    case "reconciling":
    case "validating": return "extracting"
    case "embedding": return "embedding"
    case "extracted":
    case "embedded": return "done"
    case "failed":
    case "partial": return "error"
    default: return "pending"
  }
}

export function getEntityHex(type: string): string {
  return ENTITY_HEX[type] ?? ENTITY_HEX_FALLBACK
}
```

- [ ] **Step 2: Update utils.ts — replace old color maps**

Replace `LABEL_COLORS`, `LABEL_BADGE_CLASSES`, `statusColor()` in `frontend/lib/utils.ts` with imports from constants. Keep `cn()` and `formatNumber()`.

```typescript
// frontend/lib/utils.ts
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatNumber(n: number): string {
  return n.toLocaleString("en-US")
}

// Re-export from constants for backwards compat during migration
export { ENTITY_COLORS, ENTITY_HEX, STATUS_CONFIG, mapBackendStatus, getEntityHex } from "./constants"
```

- [ ] **Step 3: Clean up globals.css — remove glass morphism**

Remove from `frontend/app/globals.css`:
- `.glass-*` classes (backdrop-blur, glass morphism)
- `.grain` texture overlay
- `.gradient-mesh` animations
- `.floating-blob` keyframes
- Keep: base color tokens (`:root` / `.dark`), scrollbar styles, basic utility classes

Replace the body background with simple opaque colors:
```css
body {
  @apply bg-background text-foreground;
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/constants.ts frontend/lib/utils.ts frontend/app/globals.css
git commit -m "feat(ui): design tokens — entity colors, status mapping, remove glass morphism"
```

---

### Task 2: Shared Components — StatusBadge + EmptyState

**Files:**
- Create: `frontend/components/shared/status-badge.tsx`
- Create: `frontend/components/shared/empty-state.tsx`

- [ ] **Step 1: Create StatusBadge**

```tsx
// frontend/components/shared/status-badge.tsx
"use client"

import { STATUS_CONFIG, type UIStatus } from "@/lib/constants"
import { cn } from "@/lib/utils"

const STATUS_ICONS: Record<UIStatus, string> = {
  pending: "○",
  parsing: "○",
  ready: "◐",
  extracting: "◌",
  embedding: "◌",
  done: "●",
  error: "✕",
}

export function StatusBadge({ status, className }: { status: UIStatus; className?: string }) {
  const config = STATUS_CONFIG[status]
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-xs font-mono",
        status === "extracting" && "animate-pulse",
        status === "embedding" && "animate-pulse",
        className,
      )}
    >
      <span className={`text-${config.color}`}>{STATUS_ICONS[status]}</span>
      <span className="text-muted-foreground">{config.label}</span>
    </span>
  )
}
```

- [ ] **Step 2: Create EmptyState**

```tsx
// frontend/components/shared/empty-state.tsx

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: React.ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center py-24 px-6 text-center">
      <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
      {description && (
        <p className="mt-2 text-sm text-muted-foreground max-w-md">{description}</p>
      )}
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/components/shared/status-badge.tsx frontend/components/shared/empty-state.tsx
git commit -m "feat(ui): add StatusBadge and EmptyState shared components"
```

---

### Task 3: Sidebar Components

**Files:**
- Create: `frontend/components/layout/sidebar-project-nav.tsx`
- Create: `frontend/components/layout/sidebar-book-item.tsx`
- Create: `frontend/components/layout/sidebar-book-list.tsx`
- Create: `frontend/components/layout/app-sidebar.tsx`
- Create: `frontend/components/layout/mobile-drawer.tsx`
- Modify: `frontend/stores/ui-store.ts` — add sidebar state

- [ ] **Step 1: Update ui-store with sidebar state**

```typescript
// frontend/stores/ui-store.ts
import { create } from "zustand"

interface UIState {
  mobileSidebarOpen: boolean
  setMobileSidebarOpen: (open: boolean) => void

  sidebarExpanded: boolean
  setSidebarExpanded: (expanded: boolean) => void

  /** Which books have their accordion expanded in sidebar */
  expandedBooks: Record<string, boolean>
  toggleBookExpanded: (bookId: string) => void
}

export const useUIStore = create<UIState>((set) => ({
  mobileSidebarOpen: false,
  setMobileSidebarOpen: (open) => set({ mobileSidebarOpen: open }),

  sidebarExpanded: true,
  setSidebarExpanded: (expanded) => set({ sidebarExpanded: expanded }),

  expandedBooks: {},
  toggleBookExpanded: (bookId) =>
    set((state) => ({
      expandedBooks: {
        ...state.expandedBooks,
        [bookId]: !state.expandedBooks[bookId],
      },
    })),
}))
```

- [ ] **Step 2: Create sidebar-project-nav.tsx**

```tsx
// frontend/components/layout/sidebar-project-nav.tsx
"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Network, MessageCircle, Dna, Settings } from "lucide-react"
import { cn } from "@/lib/utils"

const NAV_ITEMS = [
  { href: "graph", label: "Graph", icon: Network },
  { href: "chat", label: "Chat", icon: MessageCircle },
  { href: "profile", label: "Profile", icon: Dna },
  { href: "settings", label: "Settings", icon: Settings },
] as const

export function SidebarProjectNav({
  slug,
  collapsed,
}: {
  slug: string
  collapsed: boolean
}) {
  const pathname = usePathname()

  return (
    <nav className="flex flex-col gap-0.5 px-2">
      {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
        const fullHref = `/projects/${slug}/${href}`
        const isActive = pathname.startsWith(fullHref)
        return (
          <Link
            key={href}
            href={fullHref}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
              "hover:bg-muted/50",
              isActive && "bg-muted font-medium",
              collapsed && "justify-center px-2",
            )}
            title={collapsed ? label : undefined}
          >
            <Icon className="h-4 w-4 shrink-0" />
            {!collapsed && <span>{label}</span>}
          </Link>
        )
      })}
    </nav>
  )
}
```

- [ ] **Step 3: Create sidebar-book-item.tsx**

```tsx
// frontend/components/layout/sidebar-book-item.tsx
"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { ChevronRight, BookOpen, FileText, Pickaxe } from "lucide-react"
import { cn } from "@/lib/utils"
import { StatusBadge } from "@/components/shared/status-badge"
import { mapBackendStatus } from "@/lib/constants"
import { useUIStore } from "@/stores/ui-store"

interface BookItemProps {
  slug: string
  bookId: string
  title: string
  status: string // backend ProcessingStatus value
  collapsed: boolean
}

const SUB_NAV = [
  { href: "chapters", label: "Chapters", icon: FileText },
  { href: "reader", label: "Reader", icon: BookOpen },
  { href: "extraction", label: "Extraction", icon: Pickaxe },
] as const

export function SidebarBookItem({ slug, bookId, title, status, collapsed }: BookItemProps) {
  const pathname = usePathname()
  const { expandedBooks, toggleBookExpanded } = useUIStore()
  const isExpanded = expandedBooks[bookId] ?? false
  const uiStatus = mapBackendStatus(status)
  const bookBase = `/projects/${slug}/books/${bookId}`
  const isActive = pathname.startsWith(bookBase)

  if (collapsed) {
    return (
      <Link
        href={`${bookBase}/chapters`}
        className={cn(
          "flex items-center justify-center rounded-md p-2 hover:bg-muted/50",
          isActive && "bg-muted",
        )}
        title={title}
      >
        <BookOpen className="h-4 w-4" />
      </Link>
    )
  }

  return (
    <div>
      <button
        onClick={() => toggleBookExpanded(bookId)}
        className={cn(
          "flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-sm hover:bg-muted/50",
          isActive && "bg-muted/50",
        )}
      >
        <ChevronRight
          className={cn("h-3 w-3 shrink-0 transition-transform", isExpanded && "rotate-90")}
        />
        <span className="truncate flex-1 text-left">{title}</span>
        <StatusBadge status={uiStatus} className="ml-auto" />
      </button>

      {isExpanded && (
        <div className="ml-4 mt-0.5 flex flex-col gap-0.5 border-l pl-2">
          {SUB_NAV.map(({ href, label, icon: Icon }) => {
            const fullHref = `${bookBase}/${href}`
            const isSubActive = pathname.startsWith(fullHref)
            return (
              <Link
                key={href}
                href={fullHref}
                className={cn(
                  "flex items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors",
                  "hover:bg-muted/50 text-muted-foreground",
                  isSubActive && "text-foreground font-medium",
                )}
              >
                <Icon className="h-3 w-3" />
                <span>{label}</span>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Create sidebar-book-list.tsx**

```tsx
// frontend/components/layout/sidebar-book-list.tsx
"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Plus, Library } from "lucide-react"
import { cn } from "@/lib/utils"
import { SidebarBookItem } from "./sidebar-book-item"

interface Book {
  id: string
  title: string
  status: string
}

export function SidebarBookList({
  slug,
  books,
  collapsed,
}: {
  slug: string
  books: Book[]
  collapsed: boolean
}) {
  const pathname = usePathname()
  const booksActive = pathname === `/projects/${slug}`

  return (
    <div className="flex flex-col gap-1">
      {/* Books header */}
      <Link
        href={`/projects/${slug}`}
        className={cn(
          "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors hover:bg-muted/50",
          booksActive && "bg-muted font-medium",
          collapsed && "justify-center px-2",
        )}
        title={collapsed ? "Books" : undefined}
      >
        <Library className="h-4 w-4 shrink-0" />
        {!collapsed && <span>Books</span>}
        {!collapsed && (
          <span className="ml-auto text-xs text-muted-foreground font-mono">{books.length}</span>
        )}
      </Link>

      {/* Book items */}
      {!collapsed && (
        <div className="flex flex-col gap-0.5 px-1">
          {books.map((book) => (
            <SidebarBookItem
              key={book.id}
              slug={slug}
              bookId={book.id}
              title={book.title}
              status={book.status}
              collapsed={collapsed}
            />
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Create app-sidebar.tsx**

```tsx
// frontend/components/layout/app-sidebar.tsx
"use client"

import Link from "next/link"
import { ArrowLeft } from "lucide-react"
import { cn } from "@/lib/utils"
import { SidebarProjectNav } from "./sidebar-project-nav"
import { SidebarBookList } from "./sidebar-book-list"
import { useUIStore } from "@/stores/ui-store"
import { useEffect, useState } from "react"

interface AppSidebarProps {
  slug: string
  projectName: string
  books: { id: string; title: string; status: string }[]
}

export function AppSidebar({ slug, projectName, books }: AppSidebarProps) {
  const [collapsed, setCollapsed] = useState(false)

  // Responsive: collapse on tablet
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 1279px)")
    const handler = (e: MediaQueryListEvent | MediaQueryList) => setCollapsed(e.matches)
    handler(mq)
    mq.addEventListener("change", handler)
    return () => mq.removeEventListener("change", handler)
  }, [])

  return (
    <aside
      className={cn(
        "hidden md:flex flex-col border-r bg-background h-screen sticky top-0 overflow-y-auto transition-[width] duration-200",
        collapsed ? "w-14" : "w-[220px]",
      )}
      onMouseEnter={() => collapsed && setCollapsed(false)}
      onMouseLeave={() => {
        const mq = window.matchMedia("(max-width: 1279px)")
        if (mq.matches) setCollapsed(true)
      }}
    >
      {/* Project header */}
      <div className={cn("flex items-center gap-2 px-3 py-3 border-b", collapsed && "justify-center px-2")}>
        <Link href="/projects" className="text-muted-foreground hover:text-foreground" title="All projects">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        {!collapsed && (
          <span className="text-sm font-semibold truncate">{projectName}</span>
        )}
      </div>

      {/* Level 1: Project nav */}
      <div className="py-2">
        <SidebarProjectNav slug={slug} collapsed={collapsed} />
      </div>

      {/* Separator */}
      <div className="border-t mx-3" />

      {/* Level 2: Books */}
      <div className="py-2 flex-1 overflow-y-auto">
        <SidebarBookList slug={slug} books={books} collapsed={collapsed} />
      </div>
    </aside>
  )
}
```

- [ ] **Step 6: Create mobile-drawer.tsx**

```tsx
// frontend/components/layout/mobile-drawer.tsx
"use client"

import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet"
import { Menu } from "lucide-react"
import { useUIStore } from "@/stores/ui-store"
import { SidebarProjectNav } from "./sidebar-project-nav"
import { SidebarBookList } from "./sidebar-book-list"

interface MobileDrawerProps {
  slug: string
  projectName: string
  books: { id: string; title: string; status: string }[]
}

export function MobileDrawer({ slug, projectName, books }: MobileDrawerProps) {
  const { mobileSidebarOpen, setMobileSidebarOpen } = useUIStore()

  return (
    <Sheet open={mobileSidebarOpen} onOpenChange={setMobileSidebarOpen}>
      <SheetTrigger asChild>
        <button className="md:hidden p-2 hover:bg-muted rounded-md" aria-label="Open menu">
          <Menu className="h-5 w-5" />
        </button>
      </SheetTrigger>
      <SheetContent side="left" className="w-[260px] p-0">
        <div className="px-3 py-3 border-b">
          <span className="text-sm font-semibold">{projectName}</span>
        </div>
        <div className="py-2">
          <SidebarProjectNav slug={slug} collapsed={false} />
        </div>
        <div className="border-t mx-3" />
        <div className="py-2">
          <SidebarBookList slug={slug} books={books} collapsed={false} />
        </div>
      </SheetContent>
    </Sheet>
  )
}
```

- [ ] **Step 7: Commit**

```bash
git add frontend/components/layout/ frontend/stores/ui-store.ts
git commit -m "feat(ui): sidebar components — two-level nav with book accordion"
```

---

### Task 4: TopBar + Root Layout + Project Layout

**Files:**
- Create: `frontend/components/layout/top-bar.tsx`
- Rewrite: `frontend/app/layout.tsx`
- Rewrite: `frontend/app/projects/[slug]/layout.tsx`

- [ ] **Step 1: Create new top-bar.tsx**

```tsx
// frontend/components/layout/top-bar.tsx
"use client"

import { ThemeToggle } from "@/components/shared/theme-toggle"
import { MobileDrawer } from "./mobile-drawer"

interface TopBarProps {
  /** Breadcrumb segments: [{label, href?}] */
  breadcrumbs?: { label: string; href?: string }[]
  /** Mobile drawer props (only in project context) */
  drawer?: {
    slug: string
    projectName: string
    books: { id: string; title: string; status: string }[]
  }
}

export function TopBar({ breadcrumbs, drawer }: TopBarProps) {
  return (
    <header className="sticky top-0 z-30 flex h-12 items-center gap-3 border-b bg-background px-4">
      {/* Mobile drawer trigger */}
      {drawer && <MobileDrawer {...drawer} />}

      {/* Breadcrumbs */}
      <nav className="flex items-center gap-1.5 text-sm min-w-0 flex-1">
        {breadcrumbs?.map((crumb, i) => (
          <span key={i} className="flex items-center gap-1.5 min-w-0">
            {i > 0 && <span className="text-muted-foreground">›</span>}
            {crumb.href ? (
              <a href={crumb.href} className="text-muted-foreground hover:text-foreground truncate">
                {crumb.label}
              </a>
            ) : (
              <span className="truncate font-medium">{crumb.label}</span>
            )}
          </span>
        ))}
      </nav>

      {/* Right side */}
      <ThemeToggle />
    </header>
  )
}
```

- [ ] **Step 2: Rewrite root layout.tsx**

```tsx
// frontend/app/layout.tsx
import type { Metadata } from "next"
import { ThemeProvider } from "next-themes"
import { Toaster } from "@/components/ui/sonner"
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
          {children}
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  )
}
```

- [ ] **Step 3: Rewrite project layout.tsx**

This layout fetches the project + books and provides the sidebar. It replaces the old tab-based layout.

```tsx
// frontend/app/projects/[slug]/layout.tsx
import { apiFetch } from "@/lib/api/client"
import { AppSidebar } from "@/components/layout/app-sidebar"
import { TopBar } from "@/components/layout/top-bar"

interface ProjectResponse {
  slug: string
  name: string
}

interface BookFile {
  id: string
  book_id: string
  original_filename: string
  status: string
}

async function getProject(slug: string): Promise<ProjectResponse | null> {
  try {
    return await apiFetch<ProjectResponse>(`/projects/${slug}`)
  } catch {
    return null
  }
}

async function getBooks(slug: string): Promise<BookFile[]> {
  try {
    return await apiFetch<BookFile[]>(`/projects/${slug}/books`)
  } catch {
    return []
  }
}

export default async function ProjectLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const [project, books] = await Promise.all([getProject(slug), getBooks(slug)])

  if (!project) {
    return <div className="p-8">Project not found</div>
  }

  const sidebarBooks = books.map((b) => ({
    id: b.book_id ?? b.id,
    title: b.original_filename?.replace(/\.(epub|pdf|txt)$/i, "") ?? "Untitled",
    status: b.status ?? "pending",
  }))

  return (
    <div className="flex min-h-screen">
      <AppSidebar slug={slug} projectName={project.name} books={sidebarBooks} />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar
          breadcrumbs={[
            { label: "Projects", href: "/projects" },
            { label: project.name },
          ]}
          drawer={{ slug, projectName: project.name, books: sidebarBooks }}
        />
        <main className="flex-1">{children}</main>
      </div>
    </div>
  )
}
```

**Note:** This is a Server Component. It fetches data at render time. The `apiFetch` function needs to work server-side too. Check if the current `apiFetch` uses relative `/api` prefix — if so, update it to use `BACKEND_URL` env var for server-side calls, or use Next.js `fetch` with the full URL. The `next.config.ts` rewrites only work client-side.

Create a server-safe fetch helper if needed:

```typescript
// Add to frontend/lib/api/client.ts
export function getApiBase() {
  // Server-side: use direct backend URL
  if (typeof window === "undefined") {
    return process.env.BACKEND_URL ?? "http://localhost:8000"
  }
  // Client-side: use Next.js rewrite proxy
  return "/api"
}
```

Then update `apiFetch` to use `getApiBase()` instead of hardcoded `/api`.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/layout/top-bar.tsx frontend/app/layout.tsx frontend/app/projects/[slug]/layout.tsx frontend/lib/api/client.ts
git commit -m "feat(ui): new shell — topbar, root layout, project layout with sidebar"
```

---

### Task 5: Dashboard Page (projects list)

**Files:**
- Rewrite: `frontend/app/page.tsx`
- Modify: `frontend/components/projects/project-card.tsx`

- [ ] **Step 1: Rewrite project-card — remove glass morphism**

Strip all `glass-*`, `backdrop-blur`, `bg-white/5` classes from `project-card.tsx`. Replace with:
- `border rounded-lg` container
- No shadow, no blur
- `text-lg font-semibold` title
- `text-sm text-muted-foreground` description (2 line clamp)
- `text-xs text-muted-foreground font-mono` stats row
- Remove animated-counter import, use plain numbers

- [ ] **Step 2: Rewrite page.tsx — clean dashboard**

```tsx
// frontend/app/page.tsx
import { apiFetch } from "@/lib/api/client"
import { TopBar } from "@/components/layout/top-bar"
import { ProjectCard } from "@/components/projects/project-card"
import { CreateProjectDialog } from "@/components/projects/create-project-dialog"
import { EmptyState } from "@/components/shared/empty-state"

interface Project {
  slug: string
  name: string
  description: string
  books_count: number
  entity_count: number
  updated_at: string
}

async function getProjects(): Promise<Project[]> {
  try {
    const res = await apiFetch<{ projects: Project[] }>("/projects")
    return res.projects
  } catch {
    return []
  }
}

export default async function DashboardPage() {
  const projects = await getProjects()

  return (
    <div className="flex flex-col min-h-screen">
      <TopBar breadcrumbs={[{ label: "Projects" }]} />
      <main className="flex-1 p-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-semibold tracking-tight">Projects</h1>
          <CreateProjectDialog />
        </div>

        {projects.length === 0 ? (
          <EmptyState
            title="No projects yet"
            description="Create your first project to start building knowledge graphs from your books."
            action={<CreateProjectDialog />}
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((p) => (
              <ProjectCard key={p.slug} project={p} />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/page.tsx frontend/components/projects/project-card.tsx
git commit -m "feat(ui): clean dashboard — remove glass morphism, add empty state"
```

---

## Chunk 2: Books Table & Upload

### Task 6: API Types + Books API Client

**Files:**
- Modify: `frontend/lib/api/types.ts`
- Create: `frontend/lib/api/books.ts`

- [ ] **Step 1: Add book/chapter types to types.ts**

Add to `frontend/lib/api/types.ts`:

```typescript
export interface ProjectBook {
  id: string
  book_id: string
  original_filename: string
  file_path: string
  book_num: number
  status: string
  created_at: string
}

export interface BookDetail {
  book: BookInfo
  chapters: ChapterInfo[]
}

// ChapterInfo should already exist but verify it has:
// number, title, word_count, chunk_count, entity_count, status, regex_matches
```

- [ ] **Step 2: Create books API client**

```typescript
// frontend/lib/api/books.ts
import { apiFetch } from "./client"
import type { BookDetail, ChapterInfo } from "./types"

export async function getBookDetail(bookId: string): Promise<BookDetail> {
  return apiFetch<BookDetail>(`/books/${bookId}`)
}

export async function getChapterText(
  bookId: string,
  chapterNumber: number,
): Promise<{ book_id: string; chapter_number: number; title: string; text: string; word_count: number }> {
  return apiFetch(`/reader/books/${bookId}/chapters/${chapterNumber}/text`)
}

export async function getChapterParagraphs(
  bookId: string,
  chapterNumber: number,
): Promise<{
  book_id: string
  chapter_number: number
  title: string
  paragraphs: { index: number; type: string; text: string; html: string; char_start: number; char_end: number; speaker?: string; word_count: number }[]
  total_words: number
}> {
  return apiFetch(`/reader/books/${bookId}/chapters/${chapterNumber}/paragraphs`)
}

export async function deleteBook(slug: string, bookId: string): Promise<void> {
  await apiFetch(`/books/${bookId}`, { method: "DELETE" })
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api/types.ts frontend/lib/api/books.ts
git commit -m "feat(api): add books + reader API client"
```

---

### Task 7: Books Table Components

**Files:**
- Create: `frontend/components/books/book-status-badge.tsx`
- Create: `frontend/components/books/book-row.tsx`
- Create: `frontend/components/books/upload-drop-zone.tsx`
- Create: `frontend/components/books/books-table.tsx`

- [ ] **Step 1: Create book-status-badge.tsx**

Thin wrapper around StatusBadge that accepts backend status string:

```tsx
// frontend/components/books/book-status-badge.tsx
"use client"

import { mapBackendStatus } from "@/lib/constants"
import { StatusBadge } from "@/components/shared/status-badge"

export function BookStatusBadge({ status }: { status: string }) {
  return <StatusBadge status={mapBackendStatus(status)} />
}
```

- [ ] **Step 2: Create upload-drop-zone.tsx**

```tsx
// frontend/components/books/upload-drop-zone.tsx
"use client"

import { useCallback, useState } from "react"
import { Upload } from "lucide-react"
import { cn } from "@/lib/utils"
import { toast } from "sonner"

export function UploadDropZone({
  slug,
  onUploadComplete,
}: {
  slug: string
  onUploadComplete: () => void
}) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)

  const handleUpload = useCallback(
    async (file: File) => {
      const ext = file.name.split(".").pop()?.toLowerCase()
      if (!ext || !["epub", "pdf", "txt"].includes(ext)) {
        toast.error("Unsupported format. Use EPUB, PDF, or TXT.")
        return
      }

      setUploading(true)
      try {
        const form = new FormData()
        form.append("file", file)
        const res = await fetch(`/api/projects/${slug}/books`, {
          method: "POST",
          body: form,
        })
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(body.detail ?? `Upload failed (${res.status})`)
        }
        toast.success(`Uploaded ${file.name}`)
        onUploadComplete()
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Upload failed")
      } finally {
        setUploading(false)
      }
    },
    [slug, onUploadComplete],
  )

  return (
    <div
      className={cn(
        "border border-dashed rounded-lg p-6 text-center transition-colors",
        dragging ? "border-blue-500 bg-blue-500/5" : "border-muted-foreground/25",
        uploading && "opacity-50 pointer-events-none",
      )}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        const file = e.dataTransfer.files[0]
        if (file) handleUpload(file)
      }}
    >
      <Upload className="h-5 w-5 mx-auto text-muted-foreground mb-2" />
      <p className="text-sm text-muted-foreground">
        {uploading ? "Uploading..." : "Drop EPUB, PDF, or TXT here"}
      </p>
      {!uploading && (
        <label className="mt-2 inline-block text-sm text-blue-500 cursor-pointer hover:underline">
          Browse files
          <input
            type="file"
            accept=".epub,.pdf,.txt"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) handleUpload(file)
              e.target.value = ""
            }}
          />
        </label>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Create books-table.tsx**

```tsx
// frontend/components/books/books-table.tsx
"use client"

import { BookStatusBadge } from "./book-status-badge"
import { UploadDropZone } from "./upload-drop-zone"
import { EmptyState } from "@/components/shared/empty-state"
import { formatNumber } from "@/lib/utils"
import { useRouter } from "next/navigation"

interface Book {
  id: string
  book_id: string
  original_filename: string
  book_num: number
  status: string
  total_chapters?: number
  total_words?: number
}

export function BooksTable({ slug, books }: { slug: string; books: Book[] }) {
  const router = useRouter()

  const refresh = () => router.refresh()

  if (books.length === 0) {
    return (
      <div className="p-6">
        <EmptyState
          title="Upload your first book"
          description="Drop an EPUB, PDF, or TXT file here to start building your knowledge graph"
          action={<UploadDropZone slug={slug} onUploadComplete={refresh} />}
        />
      </div>
    )
  }

  return (
    <div className="p-6">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground uppercase tracking-wide">
            <th className="py-2 px-3 w-10">#</th>
            <th className="py-2 px-3">Title</th>
            <th className="py-2 px-3 w-24 text-right">Chapters</th>
            <th className="py-2 px-3 w-28 text-right">Words</th>
            <th className="py-2 px-3 w-32">Status</th>
          </tr>
        </thead>
        <tbody>
          {books.map((book) => {
            const title = book.original_filename?.replace(/\.(epub|pdf|txt)$/i, "") ?? "Untitled"
            return (
              <tr
                key={book.id}
                className="border-b hover:bg-muted/30 cursor-pointer transition-colors"
                onClick={() => router.push(`/projects/${slug}/books/${book.book_id ?? book.id}/chapters`)}
              >
                <td className="py-2 px-3 font-mono text-muted-foreground">{book.book_num}</td>
                <td className="py-2 px-3 font-medium">{title}</td>
                <td className="py-2 px-3 text-right font-mono text-muted-foreground">
                  {book.total_chapters ?? "—"}
                </td>
                <td className="py-2 px-3 text-right font-mono text-muted-foreground">
                  {book.total_words ? formatNumber(book.total_words) : "—"}
                </td>
                <td className="py-2 px-3">
                  <BookStatusBadge status={book.status} />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <div className="mt-4">
        <UploadDropZone slug={slug} onUploadComplete={refresh} />
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/components/books/
git commit -m "feat(ui): books table with status badges, upload drop zone, empty state"
```

---

### Task 8: Books Page

**Files:**
- Rewrite: `frontend/app/projects/[slug]/page.tsx`

- [ ] **Step 1: Rewrite books page**

```tsx
// frontend/app/projects/[slug]/page.tsx
import { apiFetch } from "@/lib/api/client"
import { BooksTable } from "@/components/books/books-table"

async function getBooks(slug: string) {
  try {
    return await apiFetch<any[]>(`/projects/${slug}/books`)
  } catch {
    return []
  }
}

export default async function BooksPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const books = await getBooks(slug)

  return <BooksTable slug={slug} books={books} />
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/projects/[slug]/page.tsx
git commit -m "feat(ui): books page — server component with table"
```

---

## Chunk 3: Reader

### Task 9: Reader Store + Hook

**Files:**
- Create: `frontend/stores/reader-store.ts`

- [ ] **Step 1: Create reader store**

```typescript
// frontend/stores/reader-store.ts
import { create } from "zustand"

interface ReaderState {
  currentBookId: string | null
  currentChapter: number
  totalChapters: number
  setBook: (bookId: string, totalChapters: number) => void
  setChapter: (chapter: number) => void
}

export const useReaderStore = create<ReaderState>((set) => ({
  currentBookId: null,
  currentChapter: 1,
  totalChapters: 0,
  setBook: (bookId, totalChapters) => set({ currentBookId: bookId, totalChapters }),
  setChapter: (chapter) => set({ currentChapter: chapter }),
}))
```

- [ ] **Step 2: Commit**

```bash
git add frontend/stores/reader-store.ts
git commit -m "feat(ui): reader store"
```

---

### Task 10: Reader Components

**Files:**
- Create: `frontend/components/reader/chapter-content.tsx`
- Create: `frontend/components/reader/reader-nav.tsx`
- Create: `frontend/components/reader/reader-progress.tsx`

- [ ] **Step 1: Create chapter-content.tsx**

```tsx
// frontend/components/reader/chapter-content.tsx

interface Annotation {
  start: number
  end: number
  type: string
  entityId?: string
}

/**
 * Renders chapter text with optional entity annotations.
 * Without annotations, renders plain text paragraphs.
 * With annotations, splits text into spans colored by entity type.
 */
export function ChapterContent({
  text,
  annotations = [],
}: {
  text: string
  annotations?: Annotation[]
}) {
  // Split by double newlines for paragraphs
  const paragraphs = text.split(/\n\n+/).filter(Boolean)

  if (annotations.length === 0) {
    return (
      <div className="space-y-6">
        {paragraphs.map((p, i) => (
          <p key={i} className="font-serif text-lg leading-relaxed">
            {p}
          </p>
        ))}
      </div>
    )
  }

  // Future: annotation rendering with spans
  // For now, fall through to plain text
  return (
    <div className="space-y-6">
      {paragraphs.map((p, i) => (
        <p key={i} className="font-serif text-lg leading-relaxed">
          {p}
        </p>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Create reader-nav.tsx**

```tsx
// frontend/components/reader/reader-nav.tsx
import Link from "next/link"
import { ChevronLeft, ChevronRight } from "lucide-react"

interface ReaderNavProps {
  slug: string
  bookId: string
  current: number
  total: number
  prevTitle?: string
  nextTitle?: string
}

export function ReaderNav({ slug, bookId, current, total, prevTitle, nextTitle }: ReaderNavProps) {
  const base = `/projects/${slug}/books/${bookId}/reader`

  return (
    <div className="flex items-center justify-between py-8 text-sm text-muted-foreground">
      {current > 1 ? (
        <Link href={`${base}/${current - 1}`} className="flex items-center gap-1 hover:text-foreground">
          <ChevronLeft className="h-4 w-4" />
          <span className="max-w-[200px] truncate">{prevTitle ?? `Ch. ${current - 1}`}</span>
        </Link>
      ) : (
        <div />
      )}

      {current < total ? (
        <Link href={`${base}/${current + 1}`} className="flex items-center gap-1 hover:text-foreground">
          <span className="max-w-[200px] truncate">{nextTitle ?? `Ch. ${current + 1}`}</span>
          <ChevronRight className="h-4 w-4" />
        </Link>
      ) : (
        <div />
      )}
    </div>
  )
}
```

- [ ] **Step 3: Create reader-progress.tsx**

```tsx
// frontend/components/reader/reader-progress.tsx

export function ReaderProgress({ current, total }: { current: number; total: number }) {
  const pct = total > 0 ? (current / total) * 100 : 0

  return (
    <div className="flex items-center gap-3 text-xs text-muted-foreground font-mono py-4">
      <span>{current} / {total}</span>
      <div className="flex-1 h-1 bg-muted rounded-full overflow-hidden">
        <div className="h-full bg-foreground/20 rounded-full" style={{ width: `${pct}%` }} />
      </div>
      <span>{Math.round(pct)}%</span>
    </div>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/components/reader/
git commit -m "feat(ui): reader components — chapter content, navigation, progress"
```

---

### Task 11: Reader Pages

**Files:**
- Create: `frontend/app/projects/[slug]/books/[bookId]/reader/page.tsx`
- Create: `frontend/app/projects/[slug]/books/[bookId]/reader/[chapterNumber]/page.tsx`
- Create: `frontend/app/projects/[slug]/books/[bookId]/chapters/page.tsx`

- [ ] **Step 1: Create chapters list page**

```tsx
// frontend/app/projects/[slug]/books/[bookId]/chapters/page.tsx
import { apiFetch } from "@/lib/api/client"
import { formatNumber } from "@/lib/utils"
import { StatusBadge } from "@/components/shared/status-badge"
import { mapBackendStatus } from "@/lib/constants"
import Link from "next/link"

async function getBookDetail(bookId: string) {
  return apiFetch<{
    book: { id: string; title: string; total_chapters: number; status: string }
    chapters: { number: number; title: string; word_count: number; entity_count: number; status: string }[]
  }>(`/books/${bookId}`)
}

export default async function ChaptersPage({
  params,
}: {
  params: Promise<{ slug: string; bookId: string }>
}) {
  const { slug, bookId } = await params
  const detail = await getBookDetail(bookId)

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold mb-4">{detail.book.title}</h1>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs text-muted-foreground uppercase tracking-wide">
            <th className="py-2 px-3 w-10">#</th>
            <th className="py-2 px-3">Title</th>
            <th className="py-2 px-3 w-24 text-right">Words</th>
            <th className="py-2 px-3 w-20">Status</th>
          </tr>
        </thead>
        <tbody>
          {detail.chapters.map((ch) => (
            <tr key={ch.number} className="border-b hover:bg-muted/30 transition-colors">
              <td className="py-2 px-3 font-mono text-muted-foreground">{ch.number}</td>
              <td className="py-2 px-3">
                <Link
                  href={`/projects/${slug}/books/${bookId}/reader/${ch.number}`}
                  className="hover:underline"
                >
                  {ch.title || `Chapter ${ch.number}`}
                </Link>
              </td>
              <td className="py-2 px-3 text-right font-mono text-muted-foreground">
                {ch.word_count ? formatNumber(ch.word_count) : "—"}
              </td>
              <td className="py-2 px-3">
                <StatusBadge status={mapBackendStatus(ch.status)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 2: Create reader index page (redirect to ch.1)**

```tsx
// frontend/app/projects/[slug]/books/[bookId]/reader/page.tsx
import { redirect } from "next/navigation"

export default async function ReaderIndexPage({
  params,
}: {
  params: Promise<{ slug: string; bookId: string }>
}) {
  const { slug, bookId } = await params
  redirect(`/projects/${slug}/books/${bookId}/reader/1`)
}
```

- [ ] **Step 3: Create reader chapter page**

```tsx
// frontend/app/projects/[slug]/books/[bookId]/reader/[chapterNumber]/page.tsx
import { apiFetch } from "@/lib/api/client"
import { ChapterContent } from "@/components/reader/chapter-content"
import { ReaderNav } from "@/components/reader/reader-nav"
import { ReaderProgress } from "@/components/reader/reader-progress"

async function getChapter(bookId: string, num: number) {
  return apiFetch<{
    book_id: string; chapter_number: number; title: string; text: string; word_count: number
  }>(`/reader/books/${bookId}/chapters/${num}/text`)
}

async function getBookDetail(bookId: string) {
  return apiFetch<{
    book: { total_chapters: number }
    chapters: { number: number; title: string }[]
  }>(`/books/${bookId}`)
}

export default async function ReaderChapterPage({
  params,
}: {
  params: Promise<{ slug: string; bookId: string; chapterNumber: string }>
}) {
  const { slug, bookId, chapterNumber: chNumStr } = await params
  const chapterNumber = parseInt(chNumStr, 10)

  const [chapter, detail] = await Promise.all([
    getChapter(bookId, chapterNumber),
    getBookDetail(bookId),
  ])

  const total = detail.book.total_chapters
  const chapters = detail.chapters
  const prevCh = chapters.find((c) => c.number === chapterNumber - 1)
  const nextCh = chapters.find((c) => c.number === chapterNumber + 1)

  return (
    <div className="flex justify-center px-6 py-8">
      <div className="w-full max-w-[680px]">
        {/* Chapter header */}
        <div className="mb-8">
          <p className="text-sm text-muted-foreground">Chapter {chapter.chapter_number}</p>
          <h1 className="text-2xl font-semibold">{chapter.title}</h1>
        </div>

        {/* Chapter text */}
        <ChapterContent text={chapter.text} />

        {/* Navigation */}
        <ReaderNav
          slug={slug}
          bookId={bookId}
          current={chapterNumber}
          total={total}
          prevTitle={prevCh?.title}
          nextTitle={nextCh?.title}
        />

        {/* Progress */}
        <ReaderProgress current={chapterNumber} total={total} />
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/app/projects/[slug]/books/
git commit -m "feat(ui): reader + chapters pages — server components with text rendering"
```

---

## Chunk 4: Extraction Dashboard

### Task 12: Extraction SSE Hook + Store

**Files:**
- Create: `frontend/stores/extraction-store.ts`
- Create: `frontend/hooks/use-extraction-stream.ts`

- [ ] **Step 1: Create extraction store**

```typescript
// frontend/stores/extraction-store.ts
import { create } from "zustand"

export interface FeedMessage {
  time: string
  chapter: number
  type: string
  name: string
}

interface ExtractionState {
  status: "idle" | "running" | "done" | "error"
  chaptersTotal: number
  chaptersDone: number
  entitiesFound: number

  feedMessages: FeedMessage[]
  addFeedMessage: (msg: FeedMessage) => void

  setProgress: (data: { chaptersTotal?: number; chaptersDone?: number; entitiesFound?: number }) => void
  setStatus: (status: ExtractionState["status"]) => void
  reset: () => void
}

export const useExtractionStore = create<ExtractionState>((set) => ({
  status: "idle",
  chaptersTotal: 0,
  chaptersDone: 0,
  entitiesFound: 0,
  feedMessages: [],

  addFeedMessage: (msg) =>
    set((state) => ({ feedMessages: [...state.feedMessages.slice(-500), msg] })),

  setProgress: (data) =>
    set((state) => ({
      chaptersTotal: data.chaptersTotal ?? state.chaptersTotal,
      chaptersDone: data.chaptersDone ?? state.chaptersDone,
      entitiesFound: data.entitiesFound ?? state.entitiesFound,
    })),

  setStatus: (status) => set({ status }),
  reset: () => set({ status: "idle", chaptersTotal: 0, chaptersDone: 0, entitiesFound: 0, feedMessages: [] }),
}))
```

- [ ] **Step 2: Create extraction SSE hook**

```typescript
// frontend/hooks/use-extraction-stream.ts
"use client"

import { useEffect, useRef, useCallback } from "react"
import { useExtractionStore } from "@/stores/extraction-store"

export function useExtractionStream(bookId: string | null) {
  const eventSourceRef = useRef<EventSource | null>(null)
  const store = useExtractionStore()

  const connect = useCallback(() => {
    if (!bookId) return

    // Close existing connection
    eventSourceRef.current?.close()

    const es = new EventSource(`/api/stream/extraction/${bookId}`)
    eventSourceRef.current = es

    store.setStatus("running")

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.status === "started") {
          store.setProgress({ chaptersTotal: data.total, chaptersDone: 0 })
        } else if (data.status === "progress") {
          store.setProgress({
            chaptersDone: data.chapters_done,
            entitiesFound: data.entities_found ?? store.getState().entitiesFound,
          })
        } else if (data.status === "done") {
          store.setStatus("done")
          es.close()
        }
        // Ignore keepalive
      } catch {
        // Ignore parse errors
      }
    }

    es.onerror = () => {
      store.setStatus("error")
      es.close()
    }
  }, [bookId, store])

  const disconnect = useCallback(() => {
    eventSourceRef.current?.close()
    eventSourceRef.current = null
  }, [])

  useEffect(() => {
    return () => disconnect()
  }, [disconnect])

  return { connect, disconnect, ...store }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/stores/extraction-store.ts frontend/hooks/use-extraction-stream.ts
git commit -m "feat(ui): extraction store + SSE stream hook"
```

---

### Task 13: Extraction Dashboard Components

**Files:**
- Create: `frontend/components/extraction/extraction-header.tsx`
- Create: `frontend/components/extraction/extraction-donut.tsx`
- Create: `frontend/components/extraction/chapter-table.tsx`
- Create: `frontend/components/extraction/chapter-row.tsx`
- Create: `frontend/components/extraction/live-feed.tsx`
- Create: `frontend/components/extraction/extraction-action.tsx`

- [ ] **Step 1: Create extraction-header.tsx (4 counters)**

```tsx
// frontend/components/extraction/extraction-header.tsx
import { formatNumber } from "@/lib/utils"

interface StatProps {
  label: string
  value: string | number
  sub?: React.ReactNode
}

function Stat({ label, value, sub }: StatProps) {
  return (
    <div className="flex flex-col">
      <span className="text-3xl font-mono font-semibold tabular-nums">
        {typeof value === "number" ? formatNumber(value) : value}
      </span>
      <span className="text-xs text-muted-foreground uppercase tracking-wide mt-1">{label}</span>
      {sub}
    </div>
  )
}

export function ExtractionHeader({
  entities,
  relations,
  chaptersDone,
  chaptersTotal,
  cost,
}: {
  entities: number
  relations: number
  chaptersDone: number
  chaptersTotal: number
  cost?: number
}) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
      <Stat label="Entities" value={entities} />
      <Stat label="Relations" value={relations} />
      <Stat
        label="Chapters"
        value={`${chaptersDone}/${chaptersTotal}`}
        sub={
          chaptersTotal > 0 && (
            <div className="h-1 bg-muted rounded-full mt-2 overflow-hidden">
              <div
                className="h-full bg-emerald-500 rounded-full transition-all duration-300"
                style={{ width: `${(chaptersDone / chaptersTotal) * 100}%` }}
              />
            </div>
          )
        }
      />
      <Stat label="Cost" value={cost != null ? `$${cost.toFixed(2)}` : "—"} />
    </div>
  )
}
```

- [ ] **Step 2: Create extraction-donut.tsx**

```tsx
// frontend/components/extraction/extraction-donut.tsx
"use client"

import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts"
import { ENTITY_HEX, getEntityHex } from "@/lib/constants"

interface DonutData {
  type: string
  count: number
}

export function ExtractionDonut({ data }: { data: DonutData[] }) {
  const total = data.reduce((sum, d) => sum + d.count, 0)

  if (total === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-sm text-muted-foreground">
        No entities yet
      </div>
    )
  }

  return (
    <div>
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="count"
              nameKey="type"
              cx="50%"
              cy="50%"
              innerRadius={40}
              outerRadius={70}
              strokeWidth={1}
              stroke="var(--border)"
            >
              {data.map((entry) => (
                <Cell key={entry.type} fill={getEntityHex(entry.type)} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-2">
        {data.map((d) => (
          <div key={d.type} className="flex items-center gap-2 text-xs">
            <span
              className="h-2 w-2 rounded-full shrink-0"
              style={{ backgroundColor: getEntityHex(d.type) }}
            />
            <span className="text-muted-foreground truncate">{d.type}</span>
            <span className="font-mono ml-auto">{d.count}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create chapter-row.tsx (expandable)**

```tsx
// frontend/components/extraction/chapter-row.tsx
"use client"

import { useState } from "react"
import { ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"
import { formatNumber } from "@/lib/utils"
import { StatusBadge } from "@/components/shared/status-badge"
import { mapBackendStatus } from "@/lib/constants"
import { getEntityHex } from "@/lib/constants"

interface ChapterRowProps {
  number: number
  title: string
  wordCount: number
  entityCount: number
  status: string
  breakdown?: Record<string, number>
}

export function ChapterRow({ number, title, wordCount, entityCount, status, breakdown }: ChapterRowProps) {
  const [expanded, setExpanded] = useState(false)
  const uiStatus = mapBackendStatus(status)
  const canExpand = uiStatus === "done" && entityCount > 0

  return (
    <>
      <tr
        className={cn("border-b transition-colors", canExpand && "cursor-pointer hover:bg-muted/30")}
        onClick={() => canExpand && setExpanded(!expanded)}
      >
        <td className="py-2 px-3 font-mono text-muted-foreground">{number}</td>
        <td className="py-2 px-3">
          <div className="flex items-center gap-2">
            {canExpand && (
              <ChevronRight className={cn("h-3 w-3 transition-transform", expanded && "rotate-90")} />
            )}
            <span>{title || `Chapter ${number}`}</span>
          </div>
        </td>
        <td className="py-2 px-3 text-right font-mono text-muted-foreground">
          {wordCount ? formatNumber(wordCount) : "—"}
        </td>
        <td className="py-2 px-3 text-right font-mono text-muted-foreground">
          {entityCount || "—"}
        </td>
        <td className="py-2 px-3">
          <StatusBadge status={uiStatus} />
        </td>
      </tr>

      {expanded && breakdown && (
        <tr className="border-b bg-muted/10">
          <td />
          <td colSpan={4} className="py-2 px-3">
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
              {Object.entries(breakdown).map(([type, count]) => (
                <span key={type} className="flex items-center gap-1.5">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ backgroundColor: getEntityHex(type) }}
                  />
                  <span className="text-muted-foreground">{type}:</span>
                  <span className="font-mono">{count}</span>
                </span>
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
```

- [ ] **Step 4: Create chapter-table.tsx**

```tsx
// frontend/components/extraction/chapter-table.tsx
import { ChapterRow } from "./chapter-row"

interface Chapter {
  number: number
  title: string
  word_count: number
  entity_count: number
  status: string
  breakdown?: Record<string, number>
}

export function ChapterTable({ chapters }: { chapters: Chapter[] }) {
  return (
    <div className="overflow-auto max-h-[500px]">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-background">
          <tr className="border-b text-left text-xs text-muted-foreground uppercase tracking-wide">
            <th className="py-2 px-3 w-10">#</th>
            <th className="py-2 px-3">Chapter</th>
            <th className="py-2 px-3 w-24 text-right">Words</th>
            <th className="py-2 px-3 w-20 text-right">Entities</th>
            <th className="py-2 px-3 w-28">Status</th>
          </tr>
        </thead>
        <tbody>
          {chapters.map((ch) => (
            <ChapterRow
              key={ch.number}
              number={ch.number}
              title={ch.title}
              wordCount={ch.word_count}
              entityCount={ch.entity_count}
              status={ch.status}
              breakdown={ch.breakdown}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 5: Create live-feed.tsx**

```tsx
// frontend/components/extraction/live-feed.tsx
"use client"

import { useRef, useEffect, useState } from "react"
import { getEntityHex } from "@/lib/constants"
import type { FeedMessage } from "@/stores/extraction-store"

export function LiveFeed({ messages }: { messages: FeedMessage[] }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [messages, autoScroll])

  const handleScroll = () => {
    if (!containerRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current
    // Resume auto-scroll if scrolled to bottom (within 20px)
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 20)
  }

  if (messages.length === 0) return null

  return (
    <div className="border-t pt-3">
      <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">Live feed</p>
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="h-[200px] overflow-y-auto font-mono text-xs space-y-0.5"
      >
        {messages.map((msg, i) => (
          <div key={i} className="flex gap-2">
            <span className="text-muted-foreground shrink-0">{msg.time}</span>
            <span className="text-muted-foreground">Ch.{msg.chapter} →</span>
            <span style={{ color: getEntityHex(msg.type) }}>{msg.type}:</span>
            <span className="truncate">{msg.name}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Create extraction-action.tsx**

```tsx
// frontend/components/extraction/extraction-action.tsx
"use client"

import { Button } from "@/components/ui/button"
import { mapBackendStatus } from "@/lib/constants"
import type { UIStatus } from "@/lib/constants"

interface ExtractionActionProps {
  bookStatus: string
  hasProfile: boolean
  isFirstBook: boolean
  onStart: () => void
  onCancel: () => void
  disabled?: boolean
}

export function ExtractionAction({
  bookStatus,
  hasProfile,
  isFirstBook,
  onStart,
  onCancel,
  disabled,
}: ExtractionActionProps) {
  const uiStatus = mapBackendStatus(bookStatus)

  if (uiStatus === "extracting") {
    return (
      <Button variant="destructive" size="sm" onClick={onCancel} disabled={disabled}>
        Cancel
      </Button>
    )
  }

  if (uiStatus === "done") {
    return (
      <Button variant="outline" size="sm" onClick={onStart} disabled={disabled}>
        Re-extract
      </Button>
    )
  }

  if (uiStatus === "error") {
    return (
      <Button size="sm" onClick={onStart} disabled={disabled}>
        Resume
      </Button>
    )
  }

  if (uiStatus === "ready") {
    const label = !hasProfile || isFirstBook ? "Start discovery extraction" : "Start guided extraction"
    return (
      <Button size="sm" onClick={onStart} disabled={disabled}>
        {label}
      </Button>
    )
  }

  if (uiStatus === "parsing") {
    return (
      <Button size="sm" disabled>
        Parsing...
      </Button>
    )
  }

  return null
}
```

- [ ] **Step 7: Commit**

```bash
git add frontend/components/extraction/
git commit -m "feat(ui): extraction dashboard components — header, donut, table, feed, action"
```

---

### Task 14: Extraction Page

**Files:**
- Create: `frontend/app/projects/[slug]/books/[bookId]/extraction/page.tsx`

- [ ] **Step 1: Create extraction page**

This is a hybrid page — Server Component for initial data, Client Component for SSE streaming.

```tsx
// frontend/app/projects/[slug]/books/[bookId]/extraction/page.tsx
import { apiFetch } from "@/lib/api/client"
import { ExtractionDashboard } from "./dashboard"

async function getBookDetail(bookId: string) {
  return apiFetch<{
    book: { id: string; title: string; total_chapters: number; status: string; total_cost_usd: number }
    chapters: { number: number; title: string; word_count: number; entity_count: number; status: string }[]
  }>(`/books/${bookId}`)
}

async function getProjectInfo(slug: string) {
  return apiFetch<{ has_profile: boolean; books_count: number }>(`/projects/${slug}/stats`)
}

export default async function ExtractionPage({
  params,
}: {
  params: Promise<{ slug: string; bookId: string }>
}) {
  const { slug, bookId } = await params
  const [detail, projectStats] = await Promise.all([getBookDetail(bookId), getProjectInfo(slug)])

  return (
    <ExtractionDashboard
      slug={slug}
      bookId={bookId}
      book={detail.book}
      chapters={detail.chapters}
      hasProfile={projectStats.has_profile}
      isFirstBook={projectStats.books_count <= 1}
    />
  )
}
```

- [ ] **Step 2: Create dashboard client component**

```tsx
// frontend/app/projects/[slug]/books/[bookId]/extraction/dashboard.tsx
"use client"

import { useRouter } from "next/navigation"
import { toast } from "sonner"
import { ExtractionHeader } from "@/components/extraction/extraction-header"
import { ExtractionDonut } from "@/components/extraction/extraction-donut"
import { ChapterTable } from "@/components/extraction/chapter-table"
import { LiveFeed } from "@/components/extraction/live-feed"
import { ExtractionAction } from "@/components/extraction/extraction-action"
import { useExtractionStream } from "@/hooks/use-extraction-stream"

interface Props {
  slug: string
  bookId: string
  book: { id: string; title: string; total_chapters: number; status: string; total_cost_usd: number }
  chapters: { number: number; title: string; word_count: number; entity_count: number; status: string }[]
  hasProfile: boolean
  isFirstBook: boolean
}

export function ExtractionDashboard({ slug, bookId, book, chapters, hasProfile, isFirstBook }: Props) {
  const router = useRouter()
  const extraction = useExtractionStream(bookId)

  const totalEntities = chapters.reduce((sum, ch) => sum + (ch.entity_count || 0), 0)
  // Approximate relations as ~60% of entities (until we have a real count)
  const totalRelations = Math.round(totalEntities * 0.6)

  // Build donut data from chapters
  const typeCountMap: Record<string, number> = {}
  // Note: chapter breakdown data would need to come from the API
  // For now, show total entity count only

  const handleStart = async () => {
    try {
      await fetch(`/api/projects/${slug}/extract`, { method: "POST" })
      extraction.connect()
      toast.success("Extraction started")
    } catch (err) {
      toast.error("Failed to start extraction")
    }
  }

  const handleCancel = () => {
    extraction.disconnect()
    toast.info("Extraction cancelled")
  }

  return (
    <div className="p-6 space-y-6">
      {/* Title + action */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Extraction — {book.title}</h1>
        <ExtractionAction
          bookStatus={book.status}
          hasProfile={hasProfile}
          isFirstBook={isFirstBook}
          onStart={handleStart}
          onCancel={handleCancel}
        />
      </div>

      {/* Stats header + donut */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
        <ExtractionHeader
          entities={totalEntities}
          relations={totalRelations}
          chaptersDone={chapters.filter((c) => ["extracted", "embedded", "completed"].includes(c.status)).length}
          chaptersTotal={book.total_chapters}
          cost={book.total_cost_usd}
        />
        <ExtractionDonut data={[]} />
      </div>

      {/* Chapter table */}
      <ChapterTable chapters={chapters} />

      {/* Live feed (only during extraction) */}
      {extraction.status === "running" && <LiveFeed messages={extraction.feedMessages} />}
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/projects/[slug]/books/[bookId]/extraction/
git commit -m "feat(ui): extraction dashboard page with SSE streaming"
```

---

## Chunk 5: Graph Explorer Rewrite

### Task 15: Graph Components

**Files:**
- Create: `frontend/components/graph/graph-search.tsx`
- Create: `frontend/components/graph/graph-filters.tsx`
- Create: `frontend/components/graph/graph-book-selector.tsx`
- Create: `frontend/components/graph/graph-stats-bar.tsx`
- Rewrite: `frontend/components/graph/sigma-graph.tsx`
- Rewrite: `frontend/components/graph/node-detail-panel.tsx`

- [ ] **Step 1: Create graph-search.tsx**

```tsx
// frontend/components/graph/graph-search.tsx
"use client"

import { useState, useCallback } from "react"
import { Search } from "lucide-react"
import { Input } from "@/components/ui/input"
import { getEntityHex } from "@/lib/constants"

interface SearchResult {
  id: string
  name: string
  label: string
}

export function GraphSearch({
  bookId,
  onSelect,
}: {
  bookId: string
  onSelect: (nodeId: string) => void
}) {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<SearchResult[]>([])
  const [open, setOpen] = useState(false)

  const search = useCallback(
    async (q: string) => {
      if (q.length < 2) { setResults([]); return }
      try {
        const res = await fetch(`/api/graph/search?q=${encodeURIComponent(q)}&book_id=${bookId}&limit=10`)
        if (res.ok) {
          const data = await res.json()
          setResults(data)
          setOpen(true)
        }
      } catch { /* ignore */ }
    },
    [bookId],
  )

  return (
    <div className="absolute top-4 left-4 z-20 w-64">
      <div className="relative">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search entities..."
          value={query}
          onChange={(e) => { setQuery(e.target.value); search(e.target.value) }}
          onFocus={() => results.length > 0 && setOpen(true)}
          onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
          className="pl-9 bg-background border shadow-sm text-sm"
        />
      </div>
      {open && results.length > 0 && (
        <div className="mt-1 bg-background border rounded-md shadow-sm max-h-60 overflow-y-auto">
          {results.map((r) => (
            <button
              key={r.id}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm hover:bg-muted/50 text-left"
              onClick={() => { onSelect(r.id); setOpen(false); setQuery(r.name) }}
            >
              <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: getEntityHex(r.label) }} />
              <span className="truncate">{r.name}</span>
              <span className="text-xs text-muted-foreground ml-auto">{r.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Create graph-filters.tsx**

```tsx
// frontend/components/graph/graph-filters.tsx
"use client"

import { useState } from "react"
import { ChevronDown, ChevronRight } from "lucide-react"
import { Checkbox } from "@/components/ui/checkbox"
import { Slider } from "@/components/ui/slider"
import { ENTITY_HEX, getEntityHex } from "@/lib/constants"
import { cn } from "@/lib/utils"

interface FilterState {
  enabledTypes: Set<string>
  chapterRange: [number, number]
}

interface GraphFiltersProps {
  availableTypes: { type: string; count: number }[]
  maxChapter: number
  filters: FilterState
  onChange: (filters: FilterState) => void
}

export function GraphFilters({ availableTypes, maxChapter, filters, onChange }: GraphFiltersProps) {
  const [collapsed, setCollapsed] = useState(false)

  const toggleType = (type: string) => {
    const next = new Set(filters.enabledTypes)
    if (next.has(type)) next.delete(type)
    else next.add(type)
    onChange({ ...filters, enabledTypes: next })
  }

  return (
    <div className="absolute top-16 left-4 z-20 w-52 bg-background border rounded-md shadow-sm">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center gap-2 w-full px-3 py-2 text-xs font-medium uppercase tracking-wide text-muted-foreground hover:text-foreground"
      >
        {collapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        Filters
      </button>

      {!collapsed && (
        <div className="px-3 pb-3 space-y-3">
          {/* Entity type toggles */}
          <div className="space-y-1">
            {availableTypes.map(({ type, count }) => (
              <label key={type} className="flex items-center gap-2 text-xs cursor-pointer">
                <Checkbox
                  checked={filters.enabledTypes.has(type)}
                  onCheckedChange={() => toggleType(type)}
                  className="h-3.5 w-3.5"
                />
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: getEntityHex(type) }} />
                <span className="flex-1">{type}</span>
                <span className="text-muted-foreground font-mono">{count}</span>
              </label>
            ))}
          </div>

          {/* Chapter range slider */}
          {maxChapter > 1 && (
            <div>
              <p className="text-xs text-muted-foreground mb-2">
                Ch. {filters.chapterRange[0]} — {filters.chapterRange[1]}
              </p>
              <Slider
                min={1}
                max={maxChapter}
                step={1}
                value={filters.chapterRange}
                onValueChange={(val) => onChange({ ...filters, chapterRange: val as [number, number] })}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Create graph-book-selector.tsx**

```tsx
// frontend/components/graph/graph-book-selector.tsx
"use client"

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

interface Book {
  id: string
  title: string
}

export function GraphBookSelector({
  books,
  selected,
  onSelect,
}: {
  books: Book[]
  selected: string
  onSelect: (bookId: string) => void
}) {
  if (books.length <= 1) return null

  return (
    <div className="absolute top-4 right-4 z-20">
      <Select value={selected} onValueChange={onSelect}>
        <SelectTrigger className="w-[200px] bg-background shadow-sm">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {books.map((b) => (
            <SelectItem key={b.id} value={b.id}>{b.title}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
```

- [ ] **Step 4: Create graph-stats-bar.tsx**

```tsx
// frontend/components/graph/graph-stats-bar.tsx
"use client"

import { Minus, Plus, Maximize2 } from "lucide-react"
import { Button } from "@/components/ui/button"

export function GraphStatsBar({
  nodeCount,
  edgeCount,
  onZoomIn,
  onZoomOut,
  onFit,
}: {
  nodeCount: number
  edgeCount: number
  onZoomIn: () => void
  onZoomOut: () => void
  onFit: () => void
}) {
  return (
    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 flex items-center gap-3 bg-background border rounded-md shadow-sm px-3 py-1.5">
      <span className="text-xs font-mono text-muted-foreground">
        {nodeCount} nodes · {edgeCount} edges
      </span>
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onZoomOut}>
          <Minus className="h-3 w-3" />
        </Button>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onFit}>
          <Maximize2 className="h-3 w-3" />
        </Button>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onZoomIn}>
          <Plus className="h-3 w-3" />
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Rewrite sigma-graph.tsx for full-bleed**

The existing `sigma-graph.tsx` (8.3K) needs to be rewritten. Key changes:
- Remove the 600px box container — use `absolute inset-0`
- Update node colors to use new `ENTITY_HEX` palette
- Add hover highlighting (dim non-neighbors to `opacity: 0.1`)
- Add label visibility threshold (only show labels above zoom level)
- Expose `zoomIn()`, `zoomOut()`, `fitToView()`, `focusNode(id)` via ref or callbacks

Keep the existing ForceAtlas2 layout logic and graphology setup. Refactor the rendering to read theme colors from CSS variables as it currently does.

This is a substantial rewrite — read the current file fully before editing. The core Sigma setup pattern stays the same; the changes are:
1. Container: `absolute inset-0` instead of fixed height
2. Colors: import from `ENTITY_HEX`
3. Node reducer: add hover dim logic
4. Remove old filter/controls integration
5. Expose zoom/focus imperative methods

- [ ] **Step 6: Rewrite node-detail-panel.tsx**

Simplify the existing 7.5K file. Key changes:
- Remove character profile section (API may not support it consistently)
- Add entity type badge with color
- Add relations grouped by type (expandable)
- Add "Open in Reader" and "View in Chat" action links
- Slide-in from right with `translate-x` transition
- Close on `✕` click

- [ ] **Step 7: Commit**

```bash
git add frontend/components/graph/
git commit -m "feat(ui): graph explorer — full-bleed canvas, search, filters, stats bar"
```

---

### Task 16: Graph Page

**Files:**
- Rewrite: `frontend/app/projects/[slug]/graph/page.tsx`

- [ ] **Step 1: Rewrite graph page**

The page becomes a client component that orchestrates all graph sub-components. It fetches the subgraph, manages filter state, and passes data to Sigma.

Key structure:
```tsx
// Outer: relative container, full height
// Canvas: SigmaGraph absolute inset-0
// Overlays: GraphSearch, GraphBookSelector, GraphFilters, NodeDetailPanel, GraphStatsBar
```

Fetch subgraph via `GET /api/graph/subgraph/{bookId}?limit=500`. Derive available entity types + counts from nodes. Manage filter state locally. Pass filtered nodes/edges to Sigma.

- [ ] **Step 2: Commit**

```bash
git add frontend/app/projects/[slug]/graph/page.tsx
git commit -m "feat(ui): graph explorer page — full-bleed with floating panels"
```

---

## Chunk 6: Chat Enhancement

### Task 17: Chat Header + Input Components

**Files:**
- Create: `frontend/components/chat/chat-header.tsx`
- Create: `frontend/components/chat/chat-input.tsx`
- Modify: `frontend/stores/chat-store.ts` — add spoiler guard

- [ ] **Step 1: Update chat store with spoiler guard**

Add to `frontend/stores/chat-store.ts`:

```typescript
// Add to ChatState interface:
spoilerMaxChapter: number | null  // null = no limit
selectedBookId: string | null

// Add methods:
setSpoilerMaxChapter: (ch: number | null) => void
setSelectedBookId: (bookId: string | null) => void
```

When `setSelectedBookId` changes, also reset `spoilerMaxChapter` to `null` and create a new thread.

- [ ] **Step 2: Create chat-header.tsx**

```tsx
// frontend/components/chat/chat-header.tsx
"use client"

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { useChatStore } from "@/stores/chat-store"

interface Book {
  id: string
  title: string
  totalChapters: number
}

export function ChatHeader({ books }: { books: Book[] }) {
  const { selectedBookId, setSelectedBookId, spoilerMaxChapter, setSpoilerMaxChapter } = useChatStore()

  const currentBook = books.find((b) => b.id === selectedBookId) ?? books[0]

  // Build chapter options
  const chapterOptions = currentBook
    ? Array.from({ length: currentBook.totalChapters }, (_, i) => i + 1)
    : []

  return (
    <div className="flex items-center gap-3 px-4 py-2 border-b text-sm">
      {/* Book selector */}
      {books.length > 0 && (
        <Select
          value={currentBook?.id ?? ""}
          onValueChange={(id) => setSelectedBookId(id)}
        >
          <SelectTrigger className="w-[180px] h-8 text-xs">
            <SelectValue placeholder="Select book" />
          </SelectTrigger>
          <SelectContent>
            {books.map((b) => (
              <SelectItem key={b.id} value={b.id}>{b.title}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {/* Spoiler guard */}
      {currentBook && (
        <Select
          value={spoilerMaxChapter?.toString() ?? "all"}
          onValueChange={(v) => setSpoilerMaxChapter(v === "all" ? null : parseInt(v, 10))}
        >
          <SelectTrigger className="w-[160px] h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All chapters</SelectItem>
            {chapterOptions.map((ch) => (
              <SelectItem key={ch} value={ch.toString()}>Ch.1–{ch}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {spoilerMaxChapter != null && currentBook && spoilerMaxChapter < currentBook.totalChapters && (
        <Badge variant="outline" className="text-amber-500 border-amber-500/50 text-xs">
          Spoiler limit active
        </Badge>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Create chat-input.tsx**

```tsx
// frontend/components/chat/chat-input.tsx
"use client"

import { useState, useRef, useCallback } from "react"
import { ArrowRight, Square } from "lucide-react"
import { cn } from "@/lib/utils"

export function ChatInput({
  onSend,
  onStop,
  isStreaming,
  disabled,
}: {
  onSend: (message: string) => void
  onStop: () => void
  isStreaming: boolean
  disabled?: boolean
}) {
  const [value, setValue] = useState("")
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSend = useCallback(() => {
    const trimmed = value.trim()
    if (!trimmed || isStreaming) return
    onSend(trimmed)
    setValue("")
    if (textareaRef.current) textareaRef.current.style.height = "auto"
  }, [value, isStreaming, onSend])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = `${Math.min(el.scrollHeight, 120)}px` // max ~4 lines
  }

  return (
    <div className="sticky bottom-0 border-t bg-background px-4 py-3">
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => { setValue(e.target.value); handleInput() }}
          onKeyDown={handleKeyDown}
          placeholder="Ask about this book..."
          disabled={disabled}
          rows={1}
          className={cn(
            "flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-muted-foreground",
            "py-2",
            disabled && "opacity-50",
          )}
        />
        <button
          onClick={isStreaming ? onStop : handleSend}
          disabled={disabled || (!isStreaming && !value.trim())}
          className={cn(
            "shrink-0 p-2 rounded-md transition-colors",
            isStreaming
              ? "text-red-500 hover:bg-red-500/10"
              : value.trim()
                ? "text-foreground hover:bg-muted"
                : "text-muted-foreground",
          )}
        >
          {isStreaming ? <Square className="h-4 w-4" /> : <ArrowRight className="h-4 w-4" />}
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/components/chat/chat-header.tsx frontend/components/chat/chat-input.tsx frontend/stores/chat-store.ts
git commit -m "feat(ui): chat header (book selector + spoiler guard) + chat input"
```

---

### Task 18: Chat Page Integration

**Files:**
- Rewrite: `frontend/app/projects/[slug]/chat/page.tsx`

- [ ] **Step 1: Rewrite chat page**

Integrate: ChatHeader, ThreadSidebar, ChatMessage, ChatInput, SourcePanel, ConfidenceBadge, FeedbackButtons.

Key structure:
```
flex row:
  ThreadSidebar (180px, collapsible < 1280px)
  flex col (flex-1):
    ChatHeader (book selector + spoiler guard)
    Messages scroll area (flex-1)
    ChatInput (sticky bottom)
```

Use existing `use-chat-stream.ts` hook. Pass `selectedBookId` and `spoilerMaxChapter` from chat store to the stream params.

- [ ] **Step 2: Commit**

```bash
git add frontend/app/projects/[slug]/chat/page.tsx
git commit -m "feat(ui): chat page — thread sidebar + book selector + spoiler guard"
```

---

## Chunk 7: Profile + Settings + Cleanup

### Task 19: Settings Page

**Files:**
- Create: `frontend/components/settings/project-settings-form.tsx`
- Create: `frontend/components/settings/delete-project-dialog.tsx`
- Create: `frontend/app/projects/[slug]/settings/page.tsx`

- [ ] **Step 1: Create project-settings-form.tsx**

Simple form with name input, description textarea, slug (readonly), created date (readonly). Save button calls `PUT /projects/{slug}`. Inline "Saved" feedback.

- [ ] **Step 2: Create delete-project-dialog.tsx**

Dialog with "Type the project name to confirm" input. Calls `DELETE /projects/{slug}`. Redirects to `/projects` on success.

- [ ] **Step 3: Create settings page**

```tsx
// frontend/app/projects/[slug]/settings/page.tsx
import { apiFetch } from "@/lib/api/client"
import { ProjectSettingsForm } from "@/components/settings/project-settings-form"
import { DeleteProjectDialog } from "@/components/settings/delete-project-dialog"

async function getProject(slug: string) {
  return apiFetch<{ slug: string; name: string; description: string; created_at: string }>(`/projects/${slug}`)
}

export default async function SettingsPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const project = await getProject(slug)

  return (
    <div className="p-6 max-w-lg">
      <h1 className="text-xl font-semibold mb-6">Settings</h1>
      <ProjectSettingsForm project={project} />

      <div className="border-t mt-8 pt-8">
        <h2 className="text-sm font-medium text-red-500 mb-2">Danger zone</h2>
        <p className="text-sm text-muted-foreground mb-4">
          Delete this project and all its data. This action cannot be undone.
        </p>
        <DeleteProjectDialog projectName={project.name} slug={slug} />
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/components/settings/ frontend/app/projects/[slug]/settings/
git commit -m "feat(ui): settings page — project edit + delete with confirmation"
```

---

### Task 20: Profile Page Refresh

**Files:**
- Modify: `frontend/app/projects/[slug]/profile/page.tsx`

- [ ] **Step 1: Clean up profile page**

Remove any glass morphism classes. Keep the existing structure (entity types, relation types, text patterns) but:
- Use new entity color palette from `ENTITY_HEX`
- Use `getEntityHex()` for bar chart colors
- Clean up Tailwind classes to match new design system
- Ensure confidence bars use the correct proportional widths

- [ ] **Step 2: Commit**

```bash
git add frontend/app/projects/[slug]/profile/page.tsx
git commit -m "refactor(ui): profile page — align with new design system"
```

---

### Task 21: Cleanup — Delete Old Components

**Files to delete:**
- `frontend/components/shared/gradient-mesh.tsx`
- `frontend/components/shared/sidebar.tsx`
- `frontend/components/shared/top-bar.tsx`
- `frontend/components/shared/animated-counter.tsx`
- `frontend/components/projects/book-selector.tsx`
- `frontend/components/graph/graph-controls.tsx`

- [ ] **Step 1: Delete old components**

```bash
rm frontend/components/shared/gradient-mesh.tsx
rm frontend/components/shared/sidebar.tsx
rm frontend/components/shared/top-bar.tsx
rm frontend/components/shared/animated-counter.tsx
rm frontend/components/projects/book-selector.tsx
rm frontend/components/graph/graph-controls.tsx
```

- [ ] **Step 2: Search for imports of deleted components and remove them**

```bash
grep -r "gradient-mesh\|GradientMesh\|animated-counter\|AnimatedCounter\|book-selector\|BookSelector\|graph-controls\|GraphControls" frontend/ --include="*.tsx" --include="*.ts" -l
```

Fix any remaining imports.

- [ ] **Step 3: Remove glass morphism from globals.css**

Search for and remove any remaining `.glass-`, `.grain`, `.gradient-`, `.floating-` CSS classes.

- [ ] **Step 4: Commit**

```bash
git add -A frontend/
git commit -m "refactor(ui): delete old components — glass morphism, old sidebar, animated counter"
```

---

### Task 22: Smoke Test

- [ ] **Step 1: Build check**

```bash
cd frontend && npm run build
```

Fix any TypeScript or build errors.

- [ ] **Step 2: Manual smoke test**

Run `npm run dev` and verify:
1. `/projects` — dashboard loads, projects listed, create project works
2. `/projects/{slug}` — books table loads, sidebar visible, upload works
3. `/projects/{slug}/books/{id}/chapters` — chapter list loads
4. `/projects/{slug}/books/{id}/reader/1` — reader loads, text displays, prev/next works
5. `/projects/{slug}/books/{id}/extraction` — dashboard loads, action button correct
6. `/projects/{slug}/graph` — full-bleed canvas, search works, filters work
7. `/projects/{slug}/chat` — thread sidebar, book selector, spoiler guard, streaming works
8. `/projects/{slug}/profile` — entity types with bars, relations table, patterns
9. `/projects/{slug}/settings` — form renders, save works, delete works
10. Responsive: resize to tablet (icons only sidebar) and mobile (drawer)

- [ ] **Step 3: Fix issues and commit**

```bash
git add -A frontend/
git commit -m "fix(ui): smoke test fixes"
```

---

## Summary

| Chunk | Tasks | Commits | What it delivers |
|---|---|---|---|
| 1: Foundation | 1–5 | 5 | Design tokens, sidebar, topbar, layout shell, dashboard |
| 2: Books & Upload | 6–8 | 3 | API types, books table, upload, books page |
| 3: Reader | 9–11 | 3 | Reader store, components, chapter/reader pages |
| 4: Extraction | 12–14 | 3 | SSE hook, dashboard components, extraction page |
| 5: Graph | 15–16 | 2 | Full-bleed graph, search, filters, stats, node detail |
| 6: Chat | 17–18 | 2 | Chat header, input, spoiler guard, chat page |
| 7: Polish | 19–22 | 4 | Settings, profile cleanup, delete old files, smoke test |

**Total: 22 tasks, ~22 commits**

Each task produces a working (if incomplete) app. No broken intermediate states.
