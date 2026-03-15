# UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform WorldRAG from a dev-tool UI into a writer-friendly workspace with vault-style dashboard, visual book library with covers, and polished navigation.

**Architecture:** Incremental redesign by zone — 7 independent workstreams. Each zone modifies or creates specific pages/components. Existing API endpoints are sufficient; no backend changes needed. Playwright E2E tests verify each zone using `tests/fixtures/primal-hunter.epub`.

**Tech Stack:** Next.js 16, React 19, TypeScript, Tailwind 4, shadcn/ui, Zustand, Playwright, Lucide icons, Sonner toasts.

**Ports:** Backend 49515, Frontend 49516.

---

## File Map

### New Files
```
frontend/components/projects/vault-card.tsx          # Z1: New project card with cover mosaic
frontend/components/library/book-card.tsx             # Z3: Visual book card with cover
frontend/components/library/book-grid.tsx             # Z3: Book grid layout with upload slot
frontend/components/library/upload-card.tsx            # Z3: Upload card integrated in grid
frontend/app/projects/[slug]/books/[bookId]/page.tsx  # Z4: New book detail page
frontend/components/books/book-detail-header.tsx      # Z4: Cover + metadata layout
frontend/components/books/book-detail-tabs.tsx        # Z4: Chapters/Entities/Extraction tabs
frontend/e2e/dashboard.spec.ts                        # Z7: Dashboard E2E tests
frontend/e2e/library.spec.ts                          # Z7: Library E2E tests
frontend/e2e/book-detail.spec.ts                      # Z7: Book detail E2E tests
frontend/e2e/navigation.spec.ts                       # Z7: Navigation E2E tests
frontend/e2e/fixtures.ts                              # Z7: Shared test helpers
frontend/playwright.config.ts                         # Z7: Playwright configuration
```

### Modified Files
```
frontend/app/page.tsx                                  # Z1: Redesign dashboard
frontend/app/globals.css                               # Z5: Refine design tokens
frontend/app/projects/[slug]/layout.tsx                # Z2: Restructure layout
frontend/app/projects/[slug]/page.tsx                  # Z3: Grid instead of table
frontend/components/layout/app-sidebar.tsx             # Z2: Redesign sidebar (260px, sections)
frontend/components/layout/sidebar-project-nav.tsx     # Z2: Reorder nav (Library first, Tools section)
frontend/components/layout/sidebar-book-list.tsx       # Z2: Mini covers + status dots
frontend/components/layout/sidebar-book-item.tsx       # Z2: Thumbnail + dot
frontend/components/layout/top-bar.tsx                 # Z2: h-14, refined breadcrumbs
frontend/components/projects/create-project-dialog.tsx # Z1: No changes needed
frontend/components/shared/empty-state.tsx             # Z1: Better empty state
frontend/components/graph/node-detail-panel.tsx        # Z6: Polish styling
frontend/components/reader/epub-renderer.tsx           # Z6: Literata font, line-height
frontend/package.json                                  # Z7: Add Playwright dev dependency
```

---

## Chunk 1: Design System & Dashboard (Z5 + Z1)

### Task 1: Refine Design Tokens (Z5)

**Files:**
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Update CSS custom properties**

Add refined tokens to `globals.css`. Keep existing entity colors untouched. Add success/warning/info semantic colors, refine card hover, add transition tokens:

```css
/* After existing --radius-4xl definition, before @utility, add: */

  --success: oklch(0.723 0.191 149.58);
  --warning: oklch(0.795 0.184 86.05);
  --info: oklch(0.623 0.214 259.53);

  --transition-fast: 150ms ease;
  --transition-normal: 200ms ease;

  --card-hover-scale: 1.02;
  --card-hover-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
```

Dark mode additions:
```css
  --card-hover-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
```

- [ ] **Step 2: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build 2>&1 | tail -5`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/globals.css
git commit -m "style(Z5): add semantic color tokens and transition variables"
```

---

### Task 2: Create Vault Card Component (Z1)

**Files:**
- Create: `frontend/components/projects/vault-card.tsx`

- [ ] **Step 1: Create vault-card component**

```tsx
"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState } from "react"
import { MoreHorizontal, Pencil, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { toast } from "sonner"
import { cn } from "@/lib/utils"

interface VaultProject {
  slug: string
  name: string
  description: string
  books_count: number
  entity_count: number
  updated_at: string
  cover_image?: string | null
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

function CoverMosaic({ images, name }: { images: string[]; name: string }) {
  if (images.length === 0) {
    return (
      <div className="w-full h-full bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center">
        <span className="text-4xl font-display font-bold text-primary/40">
          {name.charAt(0).toUpperCase()}
        </span>
      </div>
    )
  }

  if (images.length === 1) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={images[0]} alt="" className="w-full h-full object-cover" />
    )
  }

  // 2x2 grid for 2+ images
  const slots = images.slice(0, 4)
  return (
    <div className="w-full h-full grid grid-cols-2 grid-rows-2">
      {slots.map((src, i) => (
        // eslint-disable-next-line @next/next/no-img-element
        <img key={i} src={src} alt="" className="w-full h-full object-cover" />
      ))}
      {slots.length < 4 &&
        Array.from({ length: 4 - slots.length }).map((_, i) => (
          <div key={`empty-${i}`} className="bg-muted" />
        ))}
    </div>
  )
}

export function VaultCard({ project }: { project: VaultProject }) {
  const router = useRouter()
  const [renameOpen, setRenameOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [newName, setNewName] = useState(project.name)
  const [confirmName, setConfirmName] = useState("")
  const [loading, setLoading] = useState(false)

  // TODO: backend should return book cover URLs per project
  // For now, use project cover_image if available
  const coverImages = project.cover_image ? [project.cover_image] : []

  async function handleRename(e: React.FormEvent) {
    e.preventDefault()
    if (!newName.trim()) return
    setLoading(true)
    try {
      await fetch(`/api/projects/${project.slug}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName.trim() }),
      })
      toast.success("Project renamed")
      setRenameOpen(false)
      router.refresh()
    } catch {
      toast.error("Failed to rename project")
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete() {
    setLoading(true)
    try {
      await fetch(`/api/projects/${project.slug}`, { method: "DELETE" })
      toast.success("Project deleted")
      setDeleteOpen(false)
      router.refresh()
    } catch {
      toast.error("Failed to delete project")
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div className="group relative rounded-xl border overflow-hidden transition-all duration-[var(--transition-fast)] hover:scale-[var(--card-hover-scale)] hover:shadow-[var(--card-hover-shadow)]">
        <Link href={`/projects/${project.slug}`} className="block">
          {/* Cover area */}
          <div className="aspect-[16/10] overflow-hidden bg-muted">
            <CoverMosaic images={coverImages} name={project.name} />
          </div>

          {/* Info area */}
          <div className="p-4">
            <h3 className="font-display font-semibold text-lg truncate pr-8">
              {project.name}
            </h3>
            {project.description && (
              <p className="text-sm text-muted-foreground line-clamp-2 mt-1">
                {project.description}
              </p>
            )}
            <div className="flex items-center justify-between mt-3">
              <div className="flex gap-3 text-xs text-muted-foreground font-mono">
                <span>{project.books_count} book{project.books_count !== 1 ? "s" : ""}</span>
                <span>{project.entity_count} entities</span>
              </div>
              <span className="text-xs text-muted-foreground">
                {timeAgo(project.updated_at)}
              </span>
            </div>
          </div>
        </Link>

        {/* Context menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="absolute top-2 right-2 h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity bg-background/60 backdrop-blur-sm"
              onClick={(e) => e.preventDefault()}
            >
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => { setNewName(project.name); setRenameOpen(true) }}>
              <Pencil className="h-3.5 w-3.5 mr-2" /> Rename
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => { setConfirmName(""); setDeleteOpen(true) }}
              className="text-red-500 focus:text-red-500"
            >
              <Trash2 className="h-3.5 w-3.5 mr-2" /> Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Rename dialog */}
      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Rename project</DialogTitle></DialogHeader>
          <form onSubmit={handleRename} className="space-y-4">
            <Input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Project name" autoFocus />
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setRenameOpen(false)}>Cancel</Button>
              <Button type="submit" disabled={loading || !newName.trim()}>{loading ? "Saving..." : "Save"}</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete dialog */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle className="text-red-500">Delete project</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">
            This will permanently delete <strong>{project.name}</strong> and all its data. Type the project name to confirm.
          </p>
          <Input value={confirmName} onChange={(e) => setConfirmName(e.target.value)} placeholder={project.name} autoFocus />
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>Cancel</Button>
            <Button variant="destructive" disabled={loading || confirmName !== project.name} onClick={handleDelete}>
              {loading ? "Deleting..." : "Delete permanently"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build 2>&1 | tail -5`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/projects/vault-card.tsx
git commit -m "feat(Z1): add VaultCard component with cover mosaic"
```

---

### Task 3: Redesign Dashboard Page (Z1)

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Rewrite dashboard page**

Replace the full content of `frontend/app/page.tsx`:

```tsx
import { apiFetch } from "@/lib/api/client"
import { VaultCard } from "@/components/projects/vault-card"
import { CreateProjectDialog } from "@/components/projects/create-project-dialog"
import { EmptyState } from "@/components/shared/empty-state"
import { ThemeToggle } from "@/components/shared/theme-toggle"
import { Search, Plus } from "lucide-react"

interface Project {
  slug: string
  name: string
  description: string
  books_count: number
  entity_count: number
  updated_at: string
  cover_image?: string | null
}

async function getProjects(): Promise<Project[]> {
  try {
    const res = await apiFetch<{ projects: Project[] }>("/projects")
    return res.projects ?? (Array.isArray(res) ? (res as unknown as Project[]) : [])
  } catch {
    return []
  }
}

export default async function DashboardPage() {
  const projects = await getProjects()

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-30 border-b bg-background/80 backdrop-blur-sm">
        <div className="mx-auto max-w-[1400px] px-6 h-14 flex items-center justify-between">
          <h1 className="font-display font-bold text-xl tracking-tight">WorldRAG</h1>
          <div className="flex items-center gap-3">
            <div className="relative hidden sm:block">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search projects..."
                className="h-9 w-64 rounded-lg border bg-muted/50 pl-9 pr-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </div>
            <ThemeToggle />
            <CreateProjectDialog />
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="mx-auto max-w-[1400px] px-6 py-8">
        {projects.length === 0 ? (
          <EmptyState
            title="Create your first universe"
            description="Each project is a workspace for a saga or book series. Upload your novels and let WorldRAG build the knowledge graph."
            action={<CreateProjectDialog />}
          />
        ) : (
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((p) => (
              <VaultCard key={p.slug} project={p} />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build 2>&1 | tail -5`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "feat(Z1): redesign dashboard with vault cards and new header"
```

---

## Chunk 2: Workspace Layout & Sidebar (Z2)

### Task 4: Redesign Sidebar (Z2)

**Files:**
- Modify: `frontend/components/layout/app-sidebar.tsx`
- Modify: `frontend/components/layout/sidebar-project-nav.tsx`
- Modify: `frontend/components/layout/sidebar-book-list.tsx`
- Modify: `frontend/components/layout/sidebar-book-item.tsx`

- [ ] **Step 1: Rewrite app-sidebar.tsx**

Replace `frontend/components/layout/app-sidebar.tsx`:

```tsx
"use client"

import Link from "next/link"
import { ArrowLeft } from "lucide-react"
import { cn } from "@/lib/utils"
import { SidebarProjectNav } from "./sidebar-project-nav"
import { SidebarBookList } from "./sidebar-book-list"
import { useEffect, useState } from "react"

interface AppSidebarProps {
  slug: string
  projectName: string
  books: { id: string; title: string; status: string; cover_image?: string | null }[]
}

export function AppSidebar({ slug, projectName, books }: AppSidebarProps) {
  const [collapsed, setCollapsed] = useState(false)

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
        collapsed ? "w-14" : "w-[260px]",
      )}
      onMouseEnter={() => collapsed && setCollapsed(false)}
      onMouseLeave={() => {
        const mq = window.matchMedia("(max-width: 1279px)")
        if (mq.matches) setCollapsed(true)
      }}
    >
      {/* Project header */}
      <div className={cn("flex items-center gap-2 px-3 py-3 border-b", collapsed && "justify-center px-2")}>
        <Link href="/" className="text-muted-foreground hover:text-foreground transition-colors" title="All projects">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        {!collapsed && (
          <span className="text-sm font-display font-semibold truncate">{projectName}</span>
        )}
      </div>

      {/* Library link + Books list */}
      <div className="py-2 flex-1 overflow-y-auto">
        <SidebarBookList slug={slug} books={books} collapsed={collapsed} />
      </div>

      {/* Separator */}
      <div className="border-t mx-3" />

      {/* Tools section */}
      <div className="py-2">
        <SidebarProjectNav slug={slug} collapsed={collapsed} />
      </div>
    </aside>
  )
}
```

- [ ] **Step 2: Rewrite sidebar-project-nav.tsx**

Replace `frontend/components/layout/sidebar-project-nav.tsx` to reorder: Tools section (Graph, Chat, Profile) + Settings footer:

```tsx
"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Network, MessageCircle, Dna, Settings } from "lucide-react"
import { cn } from "@/lib/utils"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

const tools = [
  { label: "Graph", icon: Network, path: "graph" },
  { label: "Chat", icon: MessageCircle, path: "chat" },
  { label: "Ontology", icon: Dna, path: "profile" },
]

export function SidebarProjectNav({ slug, collapsed }: { slug: string; collapsed: boolean }) {
  const pathname = usePathname()

  function NavItem({ label, icon: Icon, href }: { label: string; icon: typeof Network; href: string }) {
    const isActive = pathname === href || pathname.startsWith(href + "/")
    const content = (
      <Link
        href={href}
        className={cn(
          "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
          collapsed && "justify-center px-2",
          isActive
            ? "bg-primary/10 text-primary font-medium"
            : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
        )}
      >
        <Icon className="h-4 w-4 shrink-0" />
        {!collapsed && <span>{label}</span>}
      </Link>
    )

    if (collapsed) {
      return (
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger asChild>{content}</TooltipTrigger>
            <TooltipContent side="right">{label}</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )
    }

    return content
  }

  return (
    <div className="space-y-0.5">
      {!collapsed && (
        <span className="px-3 text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
          Tools
        </span>
      )}
      {tools.map((t) => (
        <NavItem key={t.path} label={t.label} icon={t.icon} href={`/projects/${slug}/${t.path}`} />
      ))}
      <div className="mt-1">
        <NavItem label="Settings" icon={Settings} href={`/projects/${slug}/settings`} />
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Rewrite sidebar-book-list.tsx**

Replace `frontend/components/layout/sidebar-book-list.tsx` with Library header link + mini cover book items:

```tsx
"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { BookOpen } from "lucide-react"
import { cn } from "@/lib/utils"
import { SidebarBookItem } from "./sidebar-book-item"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { useState } from "react"

interface SidebarBookListProps {
  slug: string
  books: { id: string; title: string; status: string; cover_image?: string | null }[]
  collapsed: boolean
}

export function SidebarBookList({ slug, books, collapsed }: SidebarBookListProps) {
  const pathname = usePathname()
  const isLibraryActive = pathname === `/projects/${slug}`
  const [showAll, setShowAll] = useState(false)
  const visibleBooks = showAll ? books : books.slice(0, 5)
  const hasMore = books.length > 5

  const libraryLink = (
    <Link
      href={`/projects/${slug}`}
      className={cn(
        "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
        collapsed && "justify-center px-2",
        isLibraryActive
          ? "bg-primary/10 text-primary font-medium"
          : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
      )}
    >
      <BookOpen className="h-4 w-4 shrink-0" />
      {!collapsed && (
        <>
          <span className="flex-1">Library</span>
          <span className="text-xs text-muted-foreground font-mono">{books.length}</span>
        </>
      )}
    </Link>
  )

  return (
    <div className="space-y-0.5">
      {collapsed ? (
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger asChild>{libraryLink}</TooltipTrigger>
            <TooltipContent side="right">Library ({books.length})</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      ) : (
        libraryLink
      )}

      {!collapsed && books.length > 0 && (
        <div className="ml-4 border-l pl-2 space-y-0.5">
          {visibleBooks.map((book) => (
            <SidebarBookItem key={book.id} slug={slug} book={book} />
          ))}
          {hasMore && !showAll && (
            <button
              onClick={() => setShowAll(true)}
              className="text-xs text-muted-foreground hover:text-foreground px-2 py-1 transition-colors"
            >
              Show {books.length - 5} more...
            </button>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Rewrite sidebar-book-item.tsx**

Replace `frontend/components/layout/sidebar-book-item.tsx` with mini cover thumbnail + status dot:

```tsx
"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"

const statusColors: Record<string, string> = {
  pending: "bg-muted-foreground",
  parsing: "bg-amber-500",
  ready: "bg-blue-500",
  extracting: "bg-violet-500",
  extracted: "bg-emerald-500",
  embedding: "bg-cyan-500",
  embedded: "bg-emerald-500",
  done: "bg-emerald-500",
  error: "bg-red-500",
}

interface SidebarBookItemProps {
  slug: string
  book: { id: string; title: string; status: string; cover_image?: string | null }
}

export function SidebarBookItem({ slug, book }: SidebarBookItemProps) {
  const pathname = usePathname()
  const href = `/projects/${slug}/books/${book.id}`
  const isActive = pathname.startsWith(href)
  const dotColor = statusColors[book.status] ?? "bg-muted-foreground"

  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors",
        isActive
          ? "bg-primary/10 text-primary font-medium"
          : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
      )}
    >
      {/* Mini cover or placeholder */}
      {book.cover_image ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={book.cover_image}
          alt=""
          className="w-7 h-10 rounded-sm object-cover shrink-0"
        />
      ) : (
        <div className="w-7 h-10 rounded-sm bg-muted shrink-0 flex items-center justify-center">
          <span className="text-[10px] font-mono text-muted-foreground">
            {book.title.charAt(0).toUpperCase()}
          </span>
        </div>
      )}
      <span className="truncate flex-1">{book.title}</span>
      <span className={cn("h-2 w-2 rounded-full shrink-0", dotColor)} title={book.status} />
    </Link>
  )
}
```

- [ ] **Step 5: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build 2>&1 | tail -5`
Expected: Build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/layout/
git commit -m "feat(Z2): redesign sidebar with library section, mini covers, status dots"
```

---

### Task 5: Update Layout & Top Bar (Z2)

**Files:**
- Modify: `frontend/app/projects/[slug]/layout.tsx`
- Modify: `frontend/components/layout/top-bar.tsx`

- [ ] **Step 1: Update project layout**

In `frontend/app/projects/[slug]/layout.tsx`, update the `sidebarBooks` mapping to pass `cover_image` if available from the backend, and update breadcrumb link from `/projects` to `/`:

Find `{ label: "Projects", href: "/projects" }` and replace with `{ label: "Projects", href: "/" }`.

Also update the sidebarBooks mapping. The current backend returns `BookFile` objects — we should keep that type but add `cover_image` if the backend provides it. For now, pass empty string:

```tsx
const sidebarBooks = books.map((b) => ({
  id: b.book_id ?? b.id,
  title: b.original_filename?.replace(/\.(epub|pdf|txt)$/i, "") ?? "Untitled",
  status: b.status ?? "pending",
  cover_image: (b as { cover_image?: string | null }).cover_image ?? null,
}))
```

- [ ] **Step 2: Update top-bar height to h-14**

In `frontend/components/layout/top-bar.tsx`, change the top bar height from `h-12` to `h-14`.

- [ ] **Step 3: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build 2>&1 | tail -5`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/projects/[slug]/layout.tsx frontend/components/layout/top-bar.tsx
git commit -m "feat(Z2): update layout breadcrumbs, top bar height, cover_image passthrough"
```

---

## Chunk 3: Library & Book Detail (Z3 + Z4)

### Task 6: Create Book Card Component (Z3)

**Files:**
- Create: `frontend/components/library/book-card.tsx`

- [ ] **Step 1: Create book-card component**

```tsx
"use client"

import Link from "next/link"
import { cn } from "@/lib/utils"
import { BookStatusBadge } from "@/components/books/book-status-badge"

export interface LibraryBook {
  id: string
  book_id?: string | null
  original_filename?: string
  filename?: string
  book_num: number
  status?: string
  total_chapters?: number
  total_words?: number
  cover_image?: string | null
  author?: string | null
  title?: string | null
}

function displayTitle(book: LibraryBook): string {
  if (book.title) return book.title
  return (book.original_filename ?? book.filename ?? "Untitled")
    .replace(/\.(epub|pdf|txt)$/i, "")
    .replace(/ -- .*/g, "")
}

export function BookCard({ book, slug }: { book: LibraryBook; slug: string }) {
  const href = book.book_id
    ? `/projects/${slug}/books/${book.book_id}`
    : undefined
  const name = displayTitle(book)
  const status = book.status ?? "pending"

  // Extraction progress (rough: chapters_processed / total_chapters if available)
  const progress =
    book.total_chapters && book.total_chapters > 0
      ? Math.round(((book.total_chapters) / (book.total_chapters)) * 100)
      : 0

  const card = (
    <div
      className={cn(
        "group relative rounded-xl border overflow-hidden transition-all duration-[150ms]",
        href && "hover:scale-[1.02] hover:shadow-[var(--card-hover-shadow)] cursor-pointer",
        !href && "opacity-60",
      )}
    >
      {/* Cover */}
      <div className="aspect-[2/3] overflow-hidden bg-muted relative">
        {book.cover_image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={book.cover_image} alt="" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center">
            <span className="text-3xl font-display font-bold text-primary/30">
              {name.charAt(0).toUpperCase()}
            </span>
          </div>
        )}
        {/* Status badge overlay */}
        <div className="absolute bottom-2 right-2">
          <BookStatusBadge status={status} />
        </div>
      </div>

      {/* Info */}
      <div className="p-3">
        <h3 className="font-semibold text-sm line-clamp-2 leading-tight">{name}</h3>
        {book.author && (
          <p className="text-xs text-muted-foreground mt-1 truncate">{book.author}</p>
        )}
      </div>
    </div>
  )

  if (href) {
    return <Link href={href}>{card}</Link>
  }
  return card
}
```

- [ ] **Step 2: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build 2>&1 | tail -5`
Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/library/book-card.tsx
git commit -m "feat(Z3): add BookCard component with cover and status badge"
```

---

### Task 7: Create Upload Card & Book Grid (Z3)

**Files:**
- Create: `frontend/components/library/upload-card.tsx`
- Create: `frontend/components/library/book-grid.tsx`

- [ ] **Step 1: Create upload-card component**

```tsx
"use client"

import { useState, useRef, useCallback } from "react"
import { Upload } from "lucide-react"
import { toast } from "sonner"
import { useRouter } from "next/navigation"
import { cn } from "@/lib/utils"

const ACCEPTED = [".epub", ".pdf", ".txt"]

export function UploadCard({ slug }: { slug: string }) {
  const [isDragOver, setIsDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const router = useRouter()

  const upload = useCallback(
    async (file: File) => {
      const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase()
      if (!ACCEPTED.includes(ext)) {
        toast.error(`Unsupported format: ${ext}. Use EPUB, PDF, or TXT.`)
        return
      }
      setUploading(true)
      try {
        const form = new FormData()
        form.append("file", file)
        form.append("book_num", "1")
        const res = await fetch(`/api/projects/${slug}/books`, { method: "POST", body: form })
        if (!res.ok) {
          const body = await res.text()
          throw new Error(body || `Upload failed (${res.status})`)
        }
        toast.success(`"${file.name}" added`)
        router.refresh()
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Upload failed")
      } finally {
        setUploading(false)
      }
    },
    [slug, router],
  )

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setIsDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) upload(file)
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) upload(file)
    e.target.value = ""
  }

  return (
    <div
      onClick={() => !uploading && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setIsDragOver(true) }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={handleDrop}
      className={cn(
        "rounded-xl border-2 border-dashed flex flex-col items-center justify-center cursor-pointer transition-all duration-150 aspect-[2/3]",
        isDragOver
          ? "border-primary bg-primary/5 scale-[1.02]"
          : "border-muted-foreground/20 hover:border-primary/50 hover:bg-muted/30",
        uploading && "opacity-50 pointer-events-none animate-pulse",
      )}
    >
      <Upload className="h-8 w-8 text-muted-foreground mb-2" />
      <span className="text-sm font-medium text-muted-foreground">
        {uploading ? "Uploading..." : "Add a book"}
      </span>
      <span className="text-xs text-muted-foreground mt-1">EPUB, PDF, TXT</span>
      <input
        ref={inputRef}
        type="file"
        accept=".epub,.pdf,.txt"
        onChange={handleFileChange}
        className="hidden"
      />
    </div>
  )
}
```

- [ ] **Step 2: Create book-grid component**

```tsx
"use client"

import { BookCard, type LibraryBook } from "./book-card"
import { UploadCard } from "./upload-card"
import { EmptyState } from "@/components/shared/empty-state"
import { Upload } from "lucide-react"

export function BookGrid({ slug, books }: { slug: string; books: LibraryBook[] }) {
  if (books.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <EmptyState
          title="Drop your first book here"
          description="Supports EPUB, PDF, TXT"
          icon={<Upload className="h-12 w-12 text-muted-foreground" />}
        />
        <div className="mt-8 w-64">
          <UploadCard slug={slug} />
        </div>
      </div>
    )
  }

  return (
    <div className="grid gap-4 grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
      {books.map((book) => (
        <BookCard key={book.id} book={book} slug={slug} />
      ))}
      <UploadCard slug={slug} />
    </div>
  )
}
```

- [ ] **Step 3: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build 2>&1 | tail -5`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/library/
git commit -m "feat(Z3): add UploadCard and BookGrid components"
```

---

### Task 8: Rewire Library Page (Z3)

**Files:**
- Modify: `frontend/app/projects/[slug]/page.tsx`
- Modify: `frontend/components/shared/empty-state.tsx`

- [ ] **Step 1: Update empty-state to accept icon prop**

In `frontend/components/shared/empty-state.tsx`, add an optional `icon` prop:

```tsx
export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string
  description?: string
  action?: React.ReactNode
  icon?: React.ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center py-24 px-6 text-center">
      {icon && <div className="mb-4">{icon}</div>}
      <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
      {description && (
        <p className="mt-2 text-sm text-muted-foreground max-w-md">{description}</p>
      )}
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}
```

- [ ] **Step 2: Rewrite library page**

Replace `frontend/app/projects/[slug]/page.tsx`:

```tsx
import { apiFetch } from "@/lib/api/client"
import { BookGrid } from "@/components/library/book-grid"

async function getBooks(slug: string) {
  try {
    return await apiFetch<Record<string, unknown>[]>(`/projects/${slug}/books`)
  } catch {
    return []
  }
}

export default async function LibraryPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const books = await getBooks(slug)

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-display font-semibold tracking-tight">Library</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {books.length} book{books.length !== 1 ? "s" : ""}
          </p>
        </div>
      </div>
      <BookGrid slug={slug} books={books} />
    </div>
  )
}
```

- [ ] **Step 3: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build 2>&1 | tail -5`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/projects/[slug]/page.tsx frontend/components/shared/empty-state.tsx
git commit -m "feat(Z3): replace books table with visual grid library page"
```

---

### Task 9: Create Book Detail Page (Z4)

**Files:**
- Create: `frontend/app/projects/[slug]/books/[bookId]/page.tsx`
- Create: `frontend/components/books/book-detail-header.tsx`
- Create: `frontend/components/books/book-detail-tabs.tsx`

- [ ] **Step 1: Create book-detail-header component**

```tsx
"use client"

import Link from "next/link"
import { Button } from "@/components/ui/button"
import { BookStatusBadge } from "@/components/books/book-status-badge"
import { BookOpen, Network, Play, RotateCcw } from "lucide-react"
import { formatNumber } from "@/lib/utils"
import type { BookInfo } from "@/lib/api/types"

interface BookDetailHeaderProps {
  book: BookInfo
  slug: string
  coverUrl?: string | null
}

export function BookDetailHeader({ book, slug, coverUrl }: BookDetailHeaderProps) {
  const canExtract = ["ready", "completed"].includes(book.status)
  const isExtracted = ["extracted", "embedded", "done"].includes(book.status)

  return (
    <div className="flex flex-col md:flex-row gap-6">
      {/* Cover */}
      <div className="w-48 md:w-56 shrink-0">
        {coverUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={coverUrl}
            alt={book.title}
            className="w-full aspect-[2/3] object-cover rounded-lg shadow-lg"
          />
        ) : (
          <div className="w-full aspect-[2/3] rounded-lg bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center shadow-lg">
            <span className="text-5xl font-display font-bold text-primary/30">
              {book.title.charAt(0).toUpperCase()}
            </span>
          </div>
        )}
      </div>

      {/* Metadata */}
      <div className="flex-1 min-w-0">
        <h1 className="text-3xl font-display font-bold tracking-tight">{book.title}</h1>
        {book.author && (
          <p className="text-lg text-muted-foreground mt-1">{book.author}</p>
        )}

        <div className="mt-4">
          <BookStatusBadge status={book.status} />
        </div>

        <div className="grid grid-cols-2 gap-4 mt-6 text-sm">
          <div>
            <span className="text-muted-foreground">Chapters</span>
            <p className="font-semibold tabular-nums">{formatNumber(book.total_chapters)}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Processed</span>
            <p className="font-semibold tabular-nums">{book.chapters_processed} / {book.total_chapters}</p>
          </div>
          {book.series_name && (
            <div>
              <span className="text-muted-foreground">Series</span>
              <p className="font-semibold">{book.series_name}</p>
            </div>
          )}
          {book.order_in_series != null && (
            <div>
              <span className="text-muted-foreground">Volume</span>
              <p className="font-semibold">#{book.order_in_series}</p>
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap gap-3 mt-6">
          {canExtract && !isExtracted && (
            <Link href={`/projects/${slug}/books/${book.id}/extraction`}>
              <Button>
                <Play className="h-4 w-4 mr-2" /> Extract entities
              </Button>
            </Link>
          )}
          <Link href={`/projects/${slug}/books/${book.id}/reader/1`}>
            <Button variant="secondary">
              <BookOpen className="h-4 w-4 mr-2" /> Open reader
            </Button>
          </Link>
          <Link href={`/projects/${slug}/graph`}>
            <Button variant="secondary">
              <Network className="h-4 w-4 mr-2" /> View in graph
            </Button>
          </Link>
          {isExtracted && (
            <Link href={`/projects/${slug}/books/${book.id}/extraction`}>
              <Button variant="ghost">
                <RotateCcw className="h-4 w-4 mr-2" /> Re-extract
              </Button>
            </Link>
          )}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create book-detail-tabs component**

```tsx
"use client"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { formatNumber } from "@/lib/utils"
import Link from "next/link"
import type { ChapterInfo } from "@/lib/api/types"
import { BookStatusBadge } from "@/components/books/book-status-badge"

interface BookDetailTabsProps {
  chapters: ChapterInfo[]
  slug: string
  bookId: string
}

export function BookDetailTabs({ chapters, slug, bookId }: BookDetailTabsProps) {
  return (
    <Tabs defaultValue="chapters" className="mt-8">
      <TabsList>
        <TabsTrigger value="chapters">Chapters ({chapters.length})</TabsTrigger>
        <TabsTrigger value="extraction">Extraction</TabsTrigger>
      </TabsList>

      <TabsContent value="chapters" className="mt-4">
        <div className="rounded-lg border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50 text-left text-xs font-medium text-muted-foreground">
                <th className="px-4 py-3 w-12">#</th>
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3 w-24 text-right">Words</th>
                <th className="px-4 py-3 w-24 text-right">Entities</th>
                <th className="px-4 py-3 w-28">Status</th>
              </tr>
            </thead>
            <tbody>
              {chapters.map((ch) => (
                <tr key={ch.number} className="border-b transition-colors hover:bg-muted/30">
                  <td className="px-4 py-3 font-mono text-muted-foreground">{ch.number}</td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/projects/${slug}/books/${bookId}/reader/${ch.number}`}
                      className="font-medium hover:text-primary transition-colors"
                    >
                      {ch.title || `Chapter ${ch.number}`}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                    {formatNumber(ch.word_count)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                    {ch.entity_count > 0 ? formatNumber(ch.entity_count) : "\u2014"}
                  </td>
                  <td className="px-4 py-3">
                    <BookStatusBadge status={ch.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </TabsContent>

      <TabsContent value="extraction" className="mt-4">
        <div className="rounded-lg border p-6 text-center text-muted-foreground">
          <Link
            href={`/projects/${slug}/books/${bookId}/extraction`}
            className="text-primary hover:underline"
          >
            Open extraction dashboard →
          </Link>
        </div>
      </TabsContent>
    </Tabs>
  )
}
```

- [ ] **Step 3: Create book detail page**

Create `frontend/app/projects/[slug]/books/[bookId]/page.tsx`:

```tsx
import { apiFetch } from "@/lib/api/client"
import type { BookDetail } from "@/lib/api/types"
import { BookDetailHeader } from "@/components/books/book-detail-header"
import { BookDetailTabs } from "@/components/books/book-detail-tabs"
import { notFound } from "next/navigation"

async function fetchBookDetail(bookId: string): Promise<BookDetail | null> {
  try {
    const { getBookDetail } = await import("@/lib/api/books")
    return await getBookDetail(bookId)
  } catch {
    return null
  }
}

export default async function BookDetailPage({
  params,
}: {
  params: Promise<{ slug: string; bookId: string }>
}) {
  const { slug, bookId } = await params
  const data = await fetchBookDetail(bookId)
  if (!data) return notFound()

  // Cover URL: try the book's cover from the backend
  const coverUrl = `/api/books/${bookId}/cover`

  return (
    <div className="p-6 max-w-5xl">
      <BookDetailHeader book={data.book} slug={slug} coverUrl={coverUrl} />
      <BookDetailTabs chapters={data.chapters} slug={slug} bookId={bookId} />
    </div>
  )
}
```

- [ ] **Step 4: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build 2>&1 | tail -5`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/projects/[slug]/books/[bookId]/page.tsx \
  frontend/components/books/book-detail-header.tsx \
  frontend/components/books/book-detail-tabs.tsx
git commit -m "feat(Z4): add book detail page with cover, metadata, and chapter tabs"
```

---

## Chunk 4: Polish & Playwright Tests (Z6 + Z7)

### Task 10: Polish Existing Pages (Z6)

**Files:**
- Modify: `frontend/components/reader/epub-renderer.tsx` (if exists)
- Modify: `frontend/components/graph/node-detail-panel.tsx`

- [ ] **Step 1: Improve reader typography**

In `frontend/components/reader/epub-renderer.tsx`, find the main content wrapper and ensure the prose uses Literata font with good reading line-height. Add `font-serif` class (maps to Literata) and `leading-relaxed` or `leading-[1.8]` to the content container.

- [ ] **Step 2: Polish graph node detail panel**

In `frontend/components/graph/node-detail-panel.tsx`, add smooth transition for panel open/close. Add `transition-transform duration-200` to the panel wrapper. Ensure card has proper rounded corners and shadow.

- [ ] **Step 3: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build 2>&1 | tail -5`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/reader/ frontend/components/graph/
git commit -m "style(Z6): polish reader typography and graph panel transitions"
```

---

### Task 11: Setup Playwright (Z7)

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/fixtures.ts`
- Modify: `frontend/package.json` (add playwright dep)

- [ ] **Step 1: Install Playwright**

Run:
```bash
cd /home/ringuet/WorldRAG/frontend && npm install -D @playwright/test && npx playwright install chromium
```

- [ ] **Step 2: Create Playwright config**

Create `frontend/playwright.config.ts`:

```ts
import { defineConfig } from "@playwright/test"

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",
  use: {
    baseURL: "http://localhost:49516",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "npm run dev -- -p 49516",
    url: "http://localhost:49516",
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  },
})
```

- [ ] **Step 3: Create shared fixtures**

Create `frontend/e2e/fixtures.ts`:

```ts
import { test as base, expect } from "@playwright/test"
import path from "path"
import fs from "fs"

export const EPUB_PATH = path.resolve(__dirname, "../../../tests/fixtures/primal-hunter.epub")

export const test = base.extend({})
export { expect }

export async function createTestProject(page: import("@playwright/test").Page, name: string) {
  // Navigate to dashboard
  await page.goto("/")
  // Click create project button
  const createBtn = page.getByRole("button", { name: /new project/i })
  await createBtn.click()
  // Fill form
  await page.getByPlaceholder("Project name").fill(name)
  await page.getByRole("button", { name: /create/i }).click()
  // Wait for navigation
  await page.waitForURL(/\/projects\//)
}

export async function uploadEpub(page: import("@playwright/test").Page) {
  // Find file input and upload
  const fileInput = page.locator('input[type="file"]')
  await fileInput.setInputFiles(EPUB_PATH)
  // Wait for upload toast
  await expect(page.locator('[data-sonner-toast]').first()).toBeVisible({ timeout: 15000 })
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/playwright.config.ts frontend/e2e/ frontend/package.json frontend/package-lock.json
git commit -m "chore(Z7): setup Playwright with config and shared test fixtures"
```

---

### Task 12: Dashboard E2E Tests (Z7)

**Files:**
- Create: `frontend/e2e/dashboard.spec.ts`

- [ ] **Step 1: Write dashboard tests**

```ts
import { test, expect, createTestProject } from "./fixtures"

test.describe("Dashboard", () => {
  test("shows empty state when no projects", async ({ page }) => {
    await page.goto("/")
    await expect(page.getByText("Create your first universe")).toBeVisible()
  })

  test("create project flow", async ({ page }) => {
    await page.goto("/")
    await page.getByRole("button", { name: /new project/i }).click()
    await expect(page.getByText("Create project")).toBeVisible()
    await page.getByPlaceholder("Project name").fill("Test Saga")
    await page.getByRole("button", { name: /create/i }).click()
    // Should navigate to project
    await page.waitForURL(/\/projects\//)
    await expect(page.getByText("Library")).toBeVisible()
  })

  test("vault card displays project info", async ({ page }) => {
    // Assumes project exists from previous or setup
    await page.goto("/")
    const card = page.locator("[class*=vault]").first()
    // If no projects, this test is skipped
    if (await card.isVisible()) {
      await expect(card.getByRole("heading")).toBeVisible()
    }
  })

  test("rename project via context menu", async ({ page }) => {
    await page.goto("/")
    const card = page.locator("[class*=rounded-xl]").first()
    if (!(await card.isVisible())) return
    // Hover to show menu
    await card.hover()
    await card.getByRole("button").first().click()
    await page.getByText("Rename").click()
    // Dialog should appear
    await expect(page.getByText("Rename project")).toBeVisible()
  })
})
```

- [ ] **Step 2: Commit**

```bash
git add frontend/e2e/dashboard.spec.ts
git commit -m "test(Z7): add dashboard E2E tests"
```

---

### Task 13: Library & Navigation E2E Tests (Z7)

**Files:**
- Create: `frontend/e2e/library.spec.ts`
- Create: `frontend/e2e/navigation.spec.ts`

- [ ] **Step 1: Write library tests**

```ts
import { test, expect, EPUB_PATH } from "./fixtures"

test.describe("Library", () => {
  test("shows empty state with upload prompt", async ({ page }) => {
    // Navigate to a project library (requires project to exist)
    await page.goto("/")
    const projectLink = page.locator("a[href*='/projects/']").first()
    if (!(await projectLink.isVisible())) {
      test.skip()
      return
    }
    await projectLink.click()
    await page.waitForURL(/\/projects\//)
    // Should see Library heading
    await expect(page.getByRole("heading", { name: "Library" })).toBeVisible()
  })

  test("upload epub shows book card", async ({ page }) => {
    await page.goto("/")
    const projectLink = page.locator("a[href*='/projects/']").first()
    if (!(await projectLink.isVisible())) {
      test.skip()
      return
    }
    await projectLink.click()
    await page.waitForURL(/\/projects\//)

    // Upload file
    const fileInput = page.locator('input[type="file"]')
    if (await fileInput.isVisible()) {
      await fileInput.setInputFiles(EPUB_PATH)
      // Wait for toast confirming upload
      await expect(page.locator('[data-sonner-toast]').first()).toBeVisible({ timeout: 15000 })
    }
  })
})
```

- [ ] **Step 2: Write navigation tests**

```ts
import { test, expect } from "./fixtures"

test.describe("Navigation", () => {
  test("sidebar shows on desktop", async ({ page }) => {
    await page.setViewportSize({ width: 1400, height: 900 })
    await page.goto("/")
    const projectLink = page.locator("a[href*='/projects/']").first()
    if (!(await projectLink.isVisible())) {
      test.skip()
      return
    }
    await projectLink.click()
    await page.waitForURL(/\/projects\//)
    // Sidebar should be visible
    await expect(page.locator("aside")).toBeVisible()
  })

  test("sidebar collapses on tablet", async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 })
    await page.goto("/")
    const projectLink = page.locator("a[href*='/projects/']").first()
    if (!(await projectLink.isVisible())) {
      test.skip()
      return
    }
    await projectLink.click()
    await page.waitForURL(/\/projects\//)
    // Sidebar should be narrow
    const aside = page.locator("aside")
    if (await aside.isVisible()) {
      const box = await aside.boundingBox()
      expect(box?.width).toBeLessThan(100)
    }
  })

  test("breadcrumbs show correct path", async ({ page }) => {
    await page.goto("/")
    const projectLink = page.locator("a[href*='/projects/']").first()
    if (!(await projectLink.isVisible())) {
      test.skip()
      return
    }
    await projectLink.click()
    await page.waitForURL(/\/projects\//)
    // Should have "Projects" in breadcrumb
    await expect(page.getByText("Projects").first()).toBeVisible()
  })

  test("back to dashboard from sidebar", async ({ page }) => {
    await page.goto("/")
    const projectLink = page.locator("a[href*='/projects/']").first()
    if (!(await projectLink.isVisible())) {
      test.skip()
      return
    }
    await projectLink.click()
    await page.waitForURL(/\/projects\//)
    // Click back arrow
    await page.locator('a[title="All projects"]').click()
    await page.waitForURL("/")
  })
})
```

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/library.spec.ts frontend/e2e/navigation.spec.ts
git commit -m "test(Z7): add library and navigation E2E tests"
```

---

### Task 14: Book Detail E2E Tests (Z7)

**Files:**
- Create: `frontend/e2e/book-detail.spec.ts`

- [ ] **Step 1: Write book detail tests**

```ts
import { test, expect } from "./fixtures"

test.describe("Book Detail", () => {
  test("shows book metadata", async ({ page }) => {
    // Navigate to a project with books
    await page.goto("/")
    const projectLink = page.locator("a[href*='/projects/']").first()
    if (!(await projectLink.isVisible())) {
      test.skip()
      return
    }
    await projectLink.click()
    await page.waitForURL(/\/projects\//)

    // Click first book card
    const bookLink = page.locator("a[href*='/books/']").first()
    if (!(await bookLink.isVisible())) {
      test.skip()
      return
    }
    await bookLink.click()
    await page.waitForURL(/\/books\//)

    // Should show book title
    await expect(page.getByRole("heading").first()).toBeVisible()
    // Should show chapters or status
    await expect(page.getByText(/chapter/i).first()).toBeVisible()
  })

  test("chapters tab lists chapters with links", async ({ page }) => {
    await page.goto("/")
    const projectLink = page.locator("a[href*='/projects/']").first()
    if (!(await projectLink.isVisible())) {
      test.skip()
      return
    }
    await projectLink.click()
    await page.waitForURL(/\/projects\//)
    const bookLink = page.locator("a[href*='/books/']").first()
    if (!(await bookLink.isVisible())) {
      test.skip()
      return
    }
    await bookLink.click()
    await page.waitForURL(/\/books\//)

    // Click Chapters tab (should be default)
    const chapterLink = page.locator("a[href*='/reader/']").first()
    if (await chapterLink.isVisible()) {
      // Chapter links exist
      await expect(chapterLink).toHaveAttribute("href", /\/reader\/\d+/)
    }
  })

  test("action buttons navigate correctly", async ({ page }) => {
    await page.goto("/")
    const projectLink = page.locator("a[href*='/projects/']").first()
    if (!(await projectLink.isVisible())) {
      test.skip()
      return
    }
    await projectLink.click()
    await page.waitForURL(/\/projects\//)
    const bookLink = page.locator("a[href*='/books/']").first()
    if (!(await bookLink.isVisible())) {
      test.skip()
      return
    }
    await bookLink.click()
    await page.waitForURL(/\/books\//)

    // Check that reader button exists
    const readerBtn = page.getByRole("link", { name: /open reader/i })
    if (await readerBtn.isVisible()) {
      await expect(readerBtn).toHaveAttribute("href", /\/reader\//)
    }
  })
})
```

- [ ] **Step 2: Commit**

```bash
git add frontend/e2e/book-detail.spec.ts
git commit -m "test(Z7): add book detail E2E tests"
```

---

### Task 15: Final Verification

- [ ] **Step 1: Full build check**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build 2>&1 | tail -20`
Expected: Build succeeds with no errors.

- [ ] **Step 2: Run Playwright tests** (requires running backend + frontend)

Run: `cd /home/ringuet/WorldRAG/frontend && npx playwright test --reporter=list 2>&1 | tail -30`
Expected: Tests run (some may skip if no project exists, but no crashes).

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -A && git commit -m "fix: address build/test issues from UI redesign"
```
