# Graph Explorer Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the monolithic graph explorer with a modular architecture: server-side filtering via TanStack Query, progressive node loading, URL-persisted filters, keyboard shortcuts, and proper loading/error/empty states.

**Architecture:** Split the 342L page + 305L sigma component into 5 focused components (<150L each) orchestrated by a container. Data flows through TanStack Query hooks wrapping existing API endpoints. URL state via nuqs for shareable/persistent filters.

**Tech Stack:** Next.js 16 / React 19 / TypeScript, Sigma.js 3.0 + graphology, TanStack Query v5, nuqs, shadcn/ui, lucide-react

**Spec:** `docs/superpowers/specs/2026-04-02-graph-explorer-redesign.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `frontend/hooks/use-graph.ts` | TanStack Query hooks: useSubgraph, useNeighbors, useGraphSearch |
| Create | `frontend/components/graph/graph-container.tsx` | Orchestrator: URL state, queries, graphology Graph, keyboard shortcuts |
| Create | `frontend/components/graph/graph-canvas.tsx` | Sigma.js pure renderer with perf fixes |
| Create | `frontend/components/graph/graph-toolbar.tsx` | Filters + search + zoom + stats bar |
| Create | `frontend/components/graph/graph-legend.tsx` | Floating entity type legend with toggles |
| Modify | `frontend/components/graph/node-detail-panel.tsx` → rename to `graph-detail-panel.tsx` | Refactored detail panel reading from graphology |
| Modify | `frontend/app/projects/[slug]/graph/page.tsx` | Simplified to thin wrapper (~40L) |
| Delete | `frontend/components/graph/sigma-graph.tsx` | Replaced by graph-canvas.tsx |
| Delete | `frontend/components/graph/graph-filters.tsx` | Merged into graph-toolbar.tsx |
| Delete | `frontend/components/graph/graph-search.tsx` | Merged into graph-toolbar.tsx |
| Delete | `frontend/components/graph/graph-stats-bar.tsx` | Merged into graph-toolbar.tsx |
| Delete | `frontend/components/graph/graph-book-selector.tsx` | Merged into graph-toolbar.tsx |

---

### Task 1: TanStack Query hooks for graph data

**Files:**
- Create: `frontend/hooks/use-graph.ts`

- [ ] **Step 1: Create the graph hooks file**

```typescript
"use client"

import { useQuery } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api/client"
import type { GraphNode, SubgraphData } from "@/lib/api/types"

export function useSubgraph(
  bookId: string | null,
  filters?: { labels?: string[]; chapter?: number },
) {
  const labels = filters?.labels?.join(",") ?? ""
  const chapter = filters?.chapter

  return useQuery({
    queryKey: ["graph", "subgraph", bookId, labels, chapter],
    queryFn: () => {
      const params = new URLSearchParams()
      if (labels) params.set("label", labels)
      if (chapter) params.set("chapter", String(chapter))
      const q = params.toString() ? `?${params}` : ""
      return apiFetch<SubgraphData>(`/graph/subgraph/${bookId}${q}`)
    },
    enabled: !!bookId,
    staleTime: 5 * 60_000,
  })
}

export function useNeighbors(entityId: string | null) {
  return useQuery({
    queryKey: ["graph", "neighbors", entityId],
    queryFn: () =>
      apiFetch<SubgraphData>(
        `/graph/neighbors/${entityId}?depth=1&limit=50`,
      ),
    enabled: !!entityId,
    staleTime: 5 * 60_000,
  })
}

export function useGraphSearch(bookId: string | null, query: string) {
  return useQuery({
    queryKey: ["graph", "search", bookId, query],
    queryFn: () => {
      const params = new URLSearchParams({ q: query })
      if (bookId) params.set("book_id", bookId)
      params.set("limit", "10")
      return apiFetch<GraphNode[]>(`/graph/search?${params}`)
    },
    enabled: !!bookId && query.length >= 2,
    staleTime: 30_000,
  })
}
```

Note: The existing `getSubgraph()` in `lib/api/graph.ts` only accepts a single `label` string. The backend endpoint also accepts a single label. For multi-label filtering, the container will make the call without label filter and let Sigma.js hide the unwanted types via the node reducer (visual filtering). Server-side filtering applies to single-label + chapter.

- [ ] **Step 2: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/hooks/use-graph.ts
git commit -m "feat: TanStack Query hooks for graph (useSubgraph, useNeighbors, useGraphSearch)"
```

---

### Task 2: Graph canvas — Sigma.js pure renderer

**Files:**
- Create: `frontend/components/graph/graph-canvas.tsx`

This is the core rendering component. It receives a graphology Graph and renders it with Sigma.js. Zero business logic.

- [ ] **Step 1: Create the graph canvas component**

```typescript
"use client"

import { useEffect, useRef, useCallback } from "react"
import type { MultiDirectedGraph } from "graphology"
import Sigma from "sigma"
import Forceatlas2Layout from "graphology-layout-forceatlas2/worker"
import { getEntityHex, ENTITY_HEX_FALLBACK } from "@/lib/constants"

interface GraphCanvasProps {
  graph: MultiDirectedGraph | null
  selectedNodeId: string | null
  onNodeClick: (nodeId: string) => void
  onNodeDoubleClick: (nodeId: string) => void
  onCanvasClick: () => void
  zoomRef?: React.MutableRefObject<{
    zoomIn: () => void
    zoomOut: () => void
    fit: () => void
    focusNode: (nodeId: string) => void
  } | null>
  className?: string
}

const LABEL_ZOOM_THRESHOLD = 0.4
const LAYOUT_MAX_MS = 5000
const LAYOUT_CHECK_INTERVAL = 500

export function GraphCanvas({
  graph,
  selectedNodeId,
  onNodeClick,
  onNodeDoubleClick,
  onCanvasClick,
  zoomRef,
  className,
}: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const sigmaRef = useRef<Sigma | null>(null)
  const layoutRef = useRef<Forceatlas2Layout | null>(null)
  const hoveredRef = useRef<string | null>(null)
  const cameraRatioRef = useRef(1)
  // Pre-computed color map for performance (built once per graph change)
  const colorMapRef = useRef<Map<string, string>>(new Map())

  // Build color map from graph node attributes
  useEffect(() => {
    if (!graph) return
    const map = new Map<string, string>()
    graph.forEachNode((id, attrs) => {
      const label = attrs.entityType as string ?? "Concept"
      if (!map.has(label)) {
        map.set(label, getEntityHex(label))
      }
    })
    colorMapRef.current = map
  }, [graph])

  // Initialize Sigma + layout
  useEffect(() => {
    if (!containerRef.current || !graph) return

    // Clean up previous instance
    sigmaRef.current?.kill()
    layoutRef.current?.kill()

    // Resolve theme colors once (not per frame)
    const el = containerRef.current
    const bgColor = getComputedStyle(el).getPropertyValue("--background").trim() || "#09090b"
    const edgeColor = getComputedStyle(el).getPropertyValue("--muted-foreground").trim() || "#71717a"

    const sigma = new Sigma(graph, el, {
      renderLabels: true,
      labelColor: { color: getComputedStyle(el).getPropertyValue("--foreground").trim() || "#fafafa" },
      labelFont: "Inter, system-ui, sans-serif",
      labelSize: 12,
      defaultEdgeColor: edgeColor,
      defaultNodeColor: ENTITY_HEX_FALLBACK,
      // Node reducer: color by type, size by degree, label visibility
      nodeReducer: (node, data) => {
        const res = { ...data }
        const entityType = graph.getNodeAttribute(node, "entityType") as string
        res.color = colorMapRef.current.get(entityType) ?? ENTITY_HEX_FALLBACK
        const hovered = hoveredRef.current
        const selected = selectedNodeId

        if (hovered && hovered !== node && !graph.areNeighbors(hovered, node)) {
          res.color = `${res.color}33` // dim non-neighbors
          res.label = ""
        }
        if (node === selected) {
          res.highlighted = true
        }
        // Label visibility based on zoom
        if (cameraRatioRef.current > LABEL_ZOOM_THRESHOLD && node !== hovered && node !== selected) {
          res.label = ""
        }
        return res
      },
      // Edge reducer: dim when hovering/selecting
      edgeReducer: (edge, data) => {
        const res = { ...data }
        const hovered = hoveredRef.current
        if (hovered) {
          const src = graph.source(edge)
          const tgt = graph.target(edge)
          if (src !== hovered && tgt !== hovered) {
            res.hidden = true
          }
        }
        return res
      },
    })

    sigmaRef.current = sigma

    // Track camera ratio for label visibility
    sigma.getCamera().on("updated", () => {
      cameraRatioRef.current = sigma.getCamera().getState().ratio
    })

    // Hover events
    sigma.on("enterNode", ({ node }) => {
      hoveredRef.current = node
      sigma.refresh()
    })
    sigma.on("leaveNode", () => {
      hoveredRef.current = null
      sigma.refresh()
    })

    // Click events
    sigma.on("clickNode", ({ node }) => onNodeClick(node))
    sigma.on("doubleClickNode", ({ node }) => {
      // Prevent default zoom on double-click
      onNodeDoubleClick(node)
    })
    sigma.on("clickStage", () => onCanvasClick())

    // ForceAtlas2 layout with auto-stop
    const layout = new Forceatlas2Layout(graph, {
      settings: {
        gravity: 0.05,
        scalingRatio: 2,
        barnesHutOptimize: graph.order > 500,
        slowDown: 5,
      },
    })
    layoutRef.current = layout
    layout.start()

    // Auto-stop after convergence or max time
    const startTime = Date.now()
    const checkInterval = setInterval(() => {
      if (Date.now() - startTime > LAYOUT_MAX_MS) {
        layout.stop()
        clearInterval(checkInterval)
      }
    }, LAYOUT_CHECK_INTERVAL)

    // Expose imperative methods
    if (zoomRef) {
      zoomRef.current = {
        zoomIn: () => {
          const camera = sigma.getCamera()
          camera.animatedZoom({ duration: 200 })
        },
        zoomOut: () => {
          const camera = sigma.getCamera()
          camera.animatedUnzoom({ duration: 200 })
        },
        fit: () => {
          const camera = sigma.getCamera()
          camera.animatedReset({ duration: 300 })
        },
        focusNode: (nodeId: string) => {
          const attrs = graph.getNodeAttributes(nodeId)
          if (attrs) {
            sigma.getCamera().animate(
              { x: attrs.x as number, y: attrs.y as number, ratio: 0.3 },
              { duration: 500 },
            )
          }
        },
      }
    }

    return () => {
      clearInterval(checkInterval)
      layout.kill()
      sigma.kill()
      sigmaRef.current = null
      layoutRef.current = null
    }
  }, [graph, onNodeClick, onNodeDoubleClick, onCanvasClick, selectedNodeId])

  // Update highlight when selectedNodeId changes (without rebuilding sigma)
  useEffect(() => {
    sigmaRef.current?.refresh()
  }, [selectedNodeId])

  return (
    <div
      ref={containerRef}
      className={className}
      style={{ width: "100%", height: "100%" }}
      aria-label="Knowledge graph visualization"
    />
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/components/graph/graph-canvas.tsx
git commit -m "feat: graph-canvas — Sigma.js renderer with color cache, convergence-based layout"
```

---

### Task 3: Graph toolbar — filters + search + zoom

**Files:**
- Create: `frontend/components/graph/graph-toolbar.tsx`

- [ ] **Step 1: Create the toolbar component**

```typescript
"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { Search, X, Plus, Minus, Maximize2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useGraphSearch } from "@/hooks/use-graph"
import { getEntityHex, ENTITY_HEX_FALLBACK } from "@/lib/constants"
import { cn } from "@/lib/utils"

interface GraphToolbarProps {
  // Book selector
  books: Array<{ id: string; title: string }>
  selectedBookId: string
  onBookChange: (bookId: string) => void
  // Label filters
  availableLabels: string[]
  activeLabels: string[]
  onLabelsChange: (labels: string[]) => void
  // Chapter filter
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

export function GraphToolbar({
  books,
  selectedBookId,
  onBookChange,
  availableLabels,
  activeLabels,
  onLabelsChange,
  maxChapter,
  chapterFilter,
  onChapterChange,
  bookId,
  onSearchSelect,
  nodeCount,
  edgeCount,
  onZoomIn,
  onZoomOut,
  onFit,
}: GraphToolbarProps) {
  // Search state
  const [searchQuery, setSearchQuery] = useState("")
  const [debouncedQuery, setDebouncedQuery] = useState("")
  const [searchOpen, setSearchOpen] = useState(false)
  const [activeIdx, setActiveIdx] = useState(0)
  const searchRef = useRef<HTMLDivElement>(null)

  const { data: searchResults } = useGraphSearch(bookId, debouncedQuery)

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(searchQuery), 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  // Open dropdown when results arrive
  useEffect(() => {
    if (searchResults && searchResults.length > 0) {
      setSearchOpen(true)
      setActiveIdx(0)
    }
  }, [searchResults])

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setSearchOpen(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (!searchResults?.length) return
    if (e.key === "ArrowDown") {
      e.preventDefault()
      setActiveIdx((i) => Math.min(i + 1, searchResults.length - 1))
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setActiveIdx((i) => Math.max(i - 1, 0))
    } else if (e.key === "Enter" && searchResults[activeIdx]) {
      e.preventDefault()
      onSearchSelect(searchResults[activeIdx].id)
      setSearchOpen(false)
      setSearchQuery("")
    } else if (e.key === "Escape") {
      setSearchOpen(false)
    }
  }

  const toggleLabel = (label: string) => {
    if (activeLabels.includes(label)) {
      onLabelsChange(activeLabels.filter((l) => l !== label))
    } else {
      onLabelsChange([...activeLabels, label])
    }
  }

  return (
    <div className="flex items-center gap-2 flex-wrap p-2 bg-background/80 backdrop-blur border-b">
      {/* Book selector */}
      {books.length > 1 && (
        <Select value={selectedBookId} onValueChange={onBookChange}>
          <SelectTrigger className="w-40 h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {books.map((b) => (
              <SelectItem key={b.id} value={b.id}>
                {b.title}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {/* Entity type badges */}
      <div className="flex gap-1 flex-wrap">
        {availableLabels.map((label) => {
          const active = activeLabels.length === 0 || activeLabels.includes(label)
          return (
            <Badge
              key={label}
              variant={active ? "default" : "outline"}
              className="cursor-pointer text-xs transition-opacity"
              style={{
                backgroundColor: active ? getEntityHex(label) : "transparent",
                borderColor: getEntityHex(label),
                color: active ? "white" : undefined,
                opacity: active ? 1 : 0.4,
              }}
              onClick={() => toggleLabel(label)}
            >
              {label}
            </Badge>
          )
        })}
      </div>

      {/* Chapter filter */}
      {maxChapter > 1 && (
        <Select
          value={chapterFilter ? String(chapterFilter) : "all"}
          onValueChange={(v) => onChapterChange(v === "all" ? null : Number(v))}
        >
          <SelectTrigger className="w-28 h-8 text-xs">
            <SelectValue placeholder="Chapter" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All chapters</SelectItem>
            {Array.from({ length: maxChapter }, (_, i) => i + 1).map((ch) => (
              <SelectItem key={ch} value={String(ch)}>
                Ch. {ch}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {/* Separator */}
      <div className="w-px h-5 bg-border mx-1" />

      {/* Search */}
      <div ref={searchRef} className="relative">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            onFocus={() => searchResults?.length && setSearchOpen(true)}
            placeholder="Search entities..."
            className="h-8 w-48 pl-8 text-xs"
          />
          {searchQuery && (
            <button
              onClick={() => { setSearchQuery(""); setSearchOpen(false) }}
              className="absolute right-2 top-1/2 -translate-y-1/2"
            >
              <X className="h-3 w-3 text-muted-foreground" />
            </button>
          )}
        </div>

        {/* Search dropdown */}
        {searchOpen && searchResults && searchResults.length > 0 && (
          <div className="absolute top-full left-0 mt-1 w-64 max-h-60 overflow-auto bg-popover border rounded-lg shadow-lg z-50">
            {searchResults.map((result, i) => (
              <button
                key={result.id}
                className={cn(
                  "w-full text-left px-3 py-2 text-xs hover:bg-accent flex items-center gap-2",
                  i === activeIdx && "bg-accent",
                )}
                onClick={() => {
                  onSearchSelect(result.id)
                  setSearchOpen(false)
                  setSearchQuery("")
                }}
              >
                <span
                  className="h-2 w-2 rounded-full shrink-0"
                  style={{ backgroundColor: getEntityHex(result.labels?.[0] ?? "") }}
                />
                <span className="truncate font-medium">{result.name}</span>
                <span className="text-muted-foreground ml-auto">{result.labels?.[0]}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Separator */}
      <div className="w-px h-5 bg-border mx-1" />

      {/* Stats */}
      <span className="text-xs text-muted-foreground tabular-nums">
        {nodeCount.toLocaleString()} nodes · {edgeCount.toLocaleString()} edges
      </span>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Zoom controls */}
      <div className="flex gap-1">
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onZoomIn} aria-label="Zoom in">
          <Plus className="h-3.5 w-3.5" />
        </Button>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onFit} aria-label="Fit to screen">
          <Maximize2 className="h-3.5 w-3.5" />
        </Button>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onZoomOut} aria-label="Zoom out">
          <Minus className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/components/graph/graph-toolbar.tsx
git commit -m "feat: graph-toolbar — entity badges, chapter filter, debounced search, zoom controls"
```

---

### Task 4: Graph legend + detail panel refactor

**Files:**
- Create: `frontend/components/graph/graph-legend.tsx`
- Rewrite: `frontend/components/graph/graph-detail-panel.tsx` (rename from node-detail-panel.tsx)

- [ ] **Step 1: Create graph legend**

```typescript
"use client"

import { useState } from "react"
import { ChevronDown, ChevronRight } from "lucide-react"
import { getEntityHex } from "@/lib/constants"
import { cn } from "@/lib/utils"

interface GraphLegendProps {
  visibleTypes: Array<{ type: string; count: number }>
  activeLabels: string[]
  onToggle: (type: string) => void
}

export function GraphLegend({ visibleTypes, activeLabels, onToggle }: GraphLegendProps) {
  const [collapsed, setCollapsed] = useState(false)

  if (visibleTypes.length === 0) return null

  return (
    <div className="absolute bottom-4 left-4 bg-background/90 backdrop-blur border rounded-lg shadow-lg z-10 text-xs">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center gap-1.5 px-3 py-2 w-full text-left font-medium"
      >
        {collapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        Legend
        <span className="text-muted-foreground ml-1">({visibleTypes.length})</span>
      </button>

      {!collapsed && (
        <div className="px-3 pb-2 space-y-0.5 max-h-48 overflow-auto">
          {visibleTypes.map(({ type, count }) => {
            const active = activeLabels.length === 0 || activeLabels.includes(type)
            return (
              <button
                key={type}
                onClick={() => onToggle(type)}
                className={cn(
                  "flex items-center gap-2 w-full px-1.5 py-1 rounded hover:bg-accent transition-opacity",
                  !active && "opacity-40",
                )}
              >
                <span
                  className="h-2.5 w-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: getEntityHex(type) }}
                />
                <span className="flex-1 text-left">{type}</span>
                <span className="text-muted-foreground tabular-nums">{count}</span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Rewrite detail panel**

Create `frontend/components/graph/graph-detail-panel.tsx` (the old `node-detail-panel.tsx` will be deleted in the cleanup task):

```typescript
"use client"

import { useMemo } from "react"
import Link from "next/link"
import { X, Expand, BookOpen, MessageSquare, ChevronDown, ChevronRight } from "lucide-react"
import { motion, AnimatePresence } from "motion/react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { getEntityHex } from "@/lib/constants"
import type { MultiDirectedGraph } from "graphology"

interface GraphDetailPanelProps {
  nodeId: string
  bookId: string
  projectSlug: string
  graph: MultiDirectedGraph
  onClose: () => void
  onExpandNeighbors: (nodeId: string) => void
}

interface RelationGroup {
  type: string
  relations: Array<{
    targetId: string
    targetName: string
    targetType: string
    direction: "out" | "in"
    properties: Record<string, unknown>
  }>
}

export function GraphDetailPanel({
  nodeId,
  bookId,
  projectSlug,
  graph,
  onClose,
  onExpandNeighbors,
}: GraphDetailPanelProps) {
  const attrs = graph.getNodeAttributes(nodeId)
  const name = (attrs?.label as string) ?? "Unknown"
  const entityType = (attrs?.entityType as string) ?? "Concept"
  const description = attrs?.description as string | undefined

  // Group edges by type
  const relationGroups = useMemo(() => {
    const groups = new Map<string, RelationGroup["relations"]>()

    graph.forEachOutEdge(nodeId, (edge, edgeAttrs, source, target) => {
      const type = edgeAttrs.type as string ?? "RELATES_TO"
      const targetAttrs = graph.getNodeAttributes(target)
      const rels = groups.get(type) ?? []
      rels.push({
        targetId: target,
        targetName: (targetAttrs?.label as string) ?? target,
        targetType: (targetAttrs?.entityType as string) ?? "Concept",
        direction: "out",
        properties: (edgeAttrs ?? {}) as Record<string, unknown>,
      })
      groups.set(type, rels)
    })

    graph.forEachInEdge(nodeId, (edge, edgeAttrs, source) => {
      const type = edgeAttrs.type as string ?? "RELATES_TO"
      const sourceAttrs = graph.getNodeAttributes(source)
      const rels = groups.get(type) ?? []
      rels.push({
        targetId: source,
        targetName: (sourceAttrs?.label as string) ?? source,
        targetType: (sourceAttrs?.entityType as string) ?? "Concept",
        direction: "in",
        properties: (edgeAttrs ?? {}) as Record<string, unknown>,
      })
      groups.set(type, rels)
    })

    return Array.from(groups.entries()).map(([type, relations]) => ({
      type,
      relations,
    }))
  }, [graph, nodeId])

  const totalRelations = relationGroups.reduce((sum, g) => sum + g.relations.length, 0)

  return (
    <AnimatePresence>
      <motion.div
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        exit={{ x: "100%" }}
        transition={{ duration: 0.2 }}
        className="absolute top-0 right-0 w-80 h-full bg-background border-l shadow-lg z-20 flex flex-col"
      >
        {/* Header */}
        <div className="flex items-start justify-between p-4 border-b">
          <div>
            <h3 className="font-semibold text-sm">{name}</h3>
            <Badge
              variant="outline"
              className="mt-1 text-xs"
              style={{ borderColor: getEntityHex(entityType) }}
            >
              {entityType}
            </Badge>
          </div>
          <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Content */}
        <ScrollArea className="flex-1">
          <div className="p-4 space-y-4">
            {/* Description */}
            {description && (
              <p className="text-xs text-muted-foreground">{description}</p>
            )}

            {/* Relations */}
            <div>
              <h4 className="text-xs font-medium text-muted-foreground mb-2">
                Relations ({totalRelations})
              </h4>
              {relationGroups.map((group) => (
                <Collapsible key={group.type} defaultOpen={group.relations.length <= 5}>
                  <CollapsibleTrigger className="flex items-center gap-1.5 w-full py-1 text-xs font-medium hover:text-foreground text-muted-foreground">
                    <ChevronDown className="h-3 w-3 transition-transform [[data-state=closed]>&]:rotate-[-90deg]" />
                    <span className="font-mono">{group.type}</span>
                    <span className="ml-auto text-muted-foreground">({group.relations.length})</span>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <div className="ml-4 space-y-1 mt-1">
                      {group.relations.map((rel, i) => (
                        <div key={`${rel.targetId}-${i}`} className="flex items-center gap-1.5 text-xs">
                          <span className="text-muted-foreground">
                            {rel.direction === "out" ? "→" : "←"}
                          </span>
                          <span
                            className="h-1.5 w-1.5 rounded-full shrink-0"
                            style={{ backgroundColor: getEntityHex(rel.targetType) }}
                          />
                          <span className="truncate">{rel.targetName}</span>
                        </div>
                      ))}
                    </div>
                  </CollapsibleContent>
                </Collapsible>
              ))}
            </div>
          </div>
        </ScrollArea>

        {/* Actions */}
        <div className="p-3 border-t space-y-2">
          <Button
            variant="outline"
            size="sm"
            className="w-full text-xs"
            onClick={() => onExpandNeighbors(nodeId)}
          >
            <Expand className="mr-1.5 h-3 w-3" /> Expand neighbors
          </Button>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" className="flex-1 text-xs" asChild>
              <Link href={`/projects/${projectSlug}/chat?q=${encodeURIComponent(name)}`}>
                <MessageSquare className="mr-1 h-3 w-3" /> Chat
              </Link>
            </Button>
            <Button variant="ghost" size="sm" className="flex-1 text-xs" asChild>
              <Link href={`/projects/${projectSlug}/books`}>
                <BookOpen className="mr-1 h-3 w-3" /> Reader
              </Link>
            </Button>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  )
}
```

- [ ] **Step 3: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npx tsc --noEmit`

- [ ] **Step 4: Commit**

```bash
git add frontend/components/graph/graph-legend.tsx frontend/components/graph/graph-detail-panel.tsx
git commit -m "feat: graph-legend (floating toggles) + graph-detail-panel (refactored from graphology)"
```

---

### Task 5: Graph container — orchestrator with URL state

**Files:**
- Create: `frontend/components/graph/graph-container.tsx`

- [ ] **Step 1: Create the container component**

```typescript
"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { MultiDirectedGraph } from "graphology"
import { useQueryState, parseAsString, parseAsInteger } from "nuqs"
import { Loader2 } from "lucide-react"
import { useSubgraph, useNeighbors } from "@/hooks/use-graph"
import { GraphCanvas } from "./graph-canvas"
import { GraphToolbar } from "./graph-toolbar"
import { GraphDetailPanel } from "./graph-detail-panel"
import { GraphLegend } from "./graph-legend"
import { ErrorState } from "@/components/ui/error-state"
import { EmptyState } from "@/components/shared/empty-state"
import type { SubgraphData } from "@/lib/api/types"

interface GraphContainerProps {
  projectSlug: string
  bookId: string
  books: Array<{ id: string; title: string }>
  onBookChange: (bookId: string) => void
}

/** Build a graphology MultiDirectedGraph from API SubgraphData. */
function buildGraph(data: SubgraphData): MultiDirectedGraph {
  const graph = new MultiDirectedGraph()

  // Pre-compute degree for node sizing
  const degreeMap = new Map<string, number>()
  for (const edge of data.edges) {
    degreeMap.set(edge.source, (degreeMap.get(edge.source) ?? 0) + 1)
    degreeMap.set(edge.target, (degreeMap.get(edge.target) ?? 0) + 1)
  }

  for (const node of data.nodes) {
    const label = node.labels?.[0] ?? "Concept"
    const degree = degreeMap.get(node.id) ?? 0
    graph.addNode(node.id, {
      label: node.name,
      entityType: label,
      description: node.description ?? "",
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.max(3, Math.sqrt(degree + 1) * 2),
    })
  }

  for (const edge of data.edges) {
    if (graph.hasNode(edge.source) && graph.hasNode(edge.target)) {
      graph.addEdge(edge.source, edge.target, {
        type: edge.type,
        ...(edge.properties ?? {}),
      })
    }
  }

  return graph
}

/** Derive entity type counts from graph nodes. */
function deriveTypeCounts(graph: MultiDirectedGraph): Array<{ type: string; count: number }> {
  const counts = new Map<string, number>()
  graph.forEachNode((_, attrs) => {
    const t = attrs.entityType as string
    counts.set(t, (counts.get(t) ?? 0) + 1)
  })
  return Array.from(counts.entries())
    .map(([type, count]) => ({ type, count }))
    .sort((a, b) => b.count - a.count)
}

/** Derive max chapter from edge properties. */
function deriveMaxChapter(data: SubgraphData): number {
  let max = 1
  for (const edge of data.edges) {
    const ch = edge.properties?.chapter
    if (typeof ch === "number" && ch > max) max = ch
    const vf = edge.properties?.valid_from_chapter
    if (typeof vf === "number" && vf > max) max = vf
  }
  return max
}

export function GraphContainer({
  projectSlug,
  bookId,
  books,
  onBookChange,
}: GraphContainerProps) {
  // URL state
  const [labelsParam, setLabelsParam] = useQueryState("labels", parseAsString.withDefault(""))
  const [chapterParam, setChapterParam] = useQueryState("chapter", parseAsInteger)
  const [selectedNodeId, setSelectedNodeId] = useQueryState("node", parseAsString)

  const activeLabels = useMemo(
    () => (labelsParam ? labelsParam.split(",").filter(Boolean) : []),
    [labelsParam],
  )
  const chapterFilter = chapterParam ?? null

  // Data fetching — single label for server-side, visual filtering for multi-label
  const serverLabel = activeLabels.length === 1 ? activeLabels[0] : undefined
  const { data: subgraphData, isLoading, error, refetch } = useSubgraph(
    bookId,
    { labels: serverLabel ? [serverLabel] : undefined, chapter: chapterFilter ?? undefined },
  )

  // Expand state
  const [expandNodeId, setExpandNodeId] = useState<string | null>(null)
  const { data: neighborData } = useNeighbors(expandNodeId)

  // Graphology graph
  const graphRef = useRef<MultiDirectedGraph | null>(null)
  const [graph, setGraph] = useState<MultiDirectedGraph | null>(null)

  // Build graph from subgraph data
  useEffect(() => {
    if (!subgraphData) return
    const g = buildGraph(subgraphData)
    graphRef.current = g
    setGraph(g)
  }, [subgraphData])

  // Merge neighbor data into existing graph (additive)
  useEffect(() => {
    if (!neighborData || !graphRef.current) return
    const g = graphRef.current

    for (const node of neighborData.nodes) {
      if (!g.hasNode(node.id)) {
        const label = node.labels?.[0] ?? "Concept"
        g.addNode(node.id, {
          label: node.name,
          entityType: label,
          description: node.description ?? "",
          x: Math.random() * 100,
          y: Math.random() * 100,
          size: 4,
        })
      }
    }
    for (const edge of neighborData.edges) {
      if (g.hasNode(edge.source) && g.hasNode(edge.target)) {
        try {
          g.addEdge(edge.source, edge.target, {
            type: edge.type,
            ...(edge.properties ?? {}),
          })
        } catch {
          // Edge may already exist in a MultiDirectedGraph
        }
      }
    }

    setGraph(g) // trigger re-render
    setExpandNodeId(null) // reset expand trigger
  }, [neighborData])

  // Zoom ref
  const zoomRef = useRef<{
    zoomIn: () => void
    zoomOut: () => void
    fit: () => void
    focusNode: (nodeId: string) => void
  } | null>(null)

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't fire if typing in an input
      if ((e.target as HTMLElement).tagName === "INPUT") return

      switch (e.key) {
        case "+":
        case "=":
          zoomRef.current?.zoomIn()
          break
        case "-":
          zoomRef.current?.zoomOut()
          break
        case "f":
          zoomRef.current?.fit()
          break
        case "Escape":
          setSelectedNodeId(null)
          break
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [setSelectedNodeId])

  // Callbacks
  const handleNodeClick = useCallback(
    (nodeId: string) => {
      setSelectedNodeId(nodeId)
      zoomRef.current?.focusNode(nodeId)
    },
    [setSelectedNodeId],
  )

  const handleNodeDoubleClick = useCallback(
    (nodeId: string) => setExpandNodeId(nodeId),
    [],
  )

  const handleCanvasClick = useCallback(
    () => setSelectedNodeId(null),
    [setSelectedNodeId],
  )

  const handleSearchSelect = useCallback(
    (nodeId: string) => {
      setSelectedNodeId(nodeId)
      zoomRef.current?.focusNode(nodeId)
    },
    [setSelectedNodeId],
  )

  const handleLabelsChange = useCallback(
    (labels: string[]) => setLabelsParam(labels.length > 0 ? labels.join(",") : ""),
    [setLabelsParam],
  )

  const handleLegendToggle = useCallback(
    (type: string) => {
      if (activeLabels.includes(type)) {
        handleLabelsChange(activeLabels.filter((l) => l !== type))
      } else {
        handleLabelsChange([...activeLabels, type])
      }
    },
    [activeLabels, handleLabelsChange],
  )

  // Derived data
  const typeCounts = useMemo(() => (graph ? deriveTypeCounts(graph) : []), [graph])
  const availableLabels = useMemo(() => typeCounts.map((t) => t.type), [typeCounts])
  const maxChapter = useMemo(
    () => (subgraphData ? deriveMaxChapter(subgraphData) : 1),
    [subgraphData],
  )

  // Apply visual label filter (hide nodes whose type isn't in activeLabels)
  const filteredGraph = useMemo(() => {
    if (!graph || activeLabels.length === 0) return graph
    // For multi-label: we don't rebuild — sigma's nodeReducer handles visibility
    // But if we have a single label, server already filtered
    return graph
  }, [graph, activeLabels])

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return <ErrorState title="Failed to load graph" error={error as Error} onRetry={() => refetch()} />
  }

  if (!subgraphData || subgraphData.nodes.length === 0) {
    return (
      <EmptyState
        title="No entities found"
        description="Extract a book first to populate the Knowledge Graph."
      />
    )
  }

  return (
    <div className="flex flex-col h-full relative">
      <GraphToolbar
        books={books}
        selectedBookId={bookId}
        onBookChange={onBookChange}
        availableLabels={availableLabels}
        activeLabels={activeLabels}
        onLabelsChange={handleLabelsChange}
        maxChapter={maxChapter}
        chapterFilter={chapterFilter}
        onChapterChange={(ch) => setChapterParam(ch)}
        bookId={bookId}
        onSearchSelect={handleSearchSelect}
        nodeCount={graph?.order ?? 0}
        edgeCount={graph?.size ?? 0}
        onZoomIn={() => zoomRef.current?.zoomIn()}
        onZoomOut={() => zoomRef.current?.zoomOut()}
        onFit={() => zoomRef.current?.fit()}
      />

      <div className="flex-1 relative overflow-hidden">
        <GraphCanvas
          graph={filteredGraph}
          selectedNodeId={selectedNodeId}
          onNodeClick={handleNodeClick}
          onNodeDoubleClick={handleNodeDoubleClick}
          onCanvasClick={handleCanvasClick}
          zoomRef={zoomRef}
          className="absolute inset-0"
        />

        <GraphLegend
          visibleTypes={typeCounts}
          activeLabels={activeLabels}
          onToggle={handleLegendToggle}
        />

        {selectedNodeId && graph?.hasNode(selectedNodeId) && (
          <GraphDetailPanel
            nodeId={selectedNodeId}
            bookId={bookId}
            projectSlug={projectSlug}
            graph={graph}
            onClose={() => setSelectedNodeId(null)}
            onExpandNeighbors={handleNodeDoubleClick}
          />
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/components/graph/graph-container.tsx
git commit -m "feat: graph-container — orchestrator with URL state, keyboard shortcuts, progressive loading"
```

---

### Task 6: Rewrite graph page + cleanup old files

**Files:**
- Modify: `frontend/app/projects/[slug]/graph/page.tsx`
- Delete: `frontend/components/graph/sigma-graph.tsx`
- Delete: `frontend/components/graph/graph-filters.tsx`
- Delete: `frontend/components/graph/graph-search.tsx`
- Delete: `frontend/components/graph/graph-stats-bar.tsx`
- Delete: `frontend/components/graph/graph-book-selector.tsx`
- Delete: `frontend/components/graph/node-detail-panel.tsx`

- [ ] **Step 1: Rewrite the graph page**

Replace `frontend/app/projects/[slug]/graph/page.tsx`:

```typescript
"use client"

import { use, useMemo, useCallback } from "react"
import { useQueryState, parseAsString } from "nuqs"
import { Loader2 } from "lucide-react"
import { useBooks } from "@/hooks/use-books"
import { GraphContainer } from "@/components/graph/graph-container"
import { EmptyState } from "@/components/shared/empty-state"

export default function GraphPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = use(params)
  const [bookId, setBookId] = useQueryState("book", parseAsString)
  const { data: booksRaw, isLoading } = useBooks(slug)

  const books = useMemo(() => {
    if (!booksRaw) return []
    return (booksRaw as Array<Record<string, unknown>>).map((b) => ({
      id: (b.book_id as string) ?? (b.id as string) ?? "",
      title: (b.original_filename as string) ?? (b.title as string) ?? "Book",
    }))
  }, [booksRaw])

  // Auto-select first book if none selected
  const effectiveBookId = bookId ?? books[0]?.id ?? null

  const handleBookChange = useCallback(
    (id: string) => setBookId(id),
    [setBookId],
  )

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (books.length === 0) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
        <EmptyState
          title="No books in this project"
          description="Upload and extract a book to explore its Knowledge Graph."
        />
      </div>
    )
  }

  if (!effectiveBookId) return null

  return (
    <div className="h-[calc(100vh-4rem)]">
      <GraphContainer
        projectSlug={slug}
        bookId={effectiveBookId}
        books={books}
        onBookChange={handleBookChange}
      />
    </div>
  )
}
```

- [ ] **Step 2: Delete old files**

```bash
rm frontend/components/graph/sigma-graph.tsx
rm frontend/components/graph/graph-filters.tsx
rm frontend/components/graph/graph-search.tsx
rm frontend/components/graph/graph-stats-bar.tsx
rm frontend/components/graph/graph-book-selector.tsx
rm frontend/components/graph/node-detail-panel.tsx
```

- [ ] **Step 3: Find and fix broken imports**

Run: `cd /home/ringuet/WorldRAG/frontend && grep -r "sigma-graph\|graph-filters\|graph-search\|graph-stats-bar\|graph-book-selector\|node-detail-panel\|NodeDetailPanel\|SigmaGraph\|GraphSearch\|GraphFilters\|GraphStatsBar\|GraphBookSelector" --include="*.ts" --include="*.tsx" -l`

Fix any remaining imports in other files.

- [ ] **Step 4: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build`

- [ ] **Step 5: Lint**

Run: `cd /home/ringuet/WorldRAG/frontend && npx next lint`
Fix any errors.

- [ ] **Step 6: Commit**

```bash
git add -A frontend/
git commit -m "feat: rewrite graph page, delete old components (sigma-graph, filters, search, stats-bar, book-selector, node-detail-panel)"
```

---

### Task 7: Integration verification

- [ ] **Step 1: Run backend tests**

Run: `cd /home/ringuet/WorldRAG && uv run pytest backend/tests/ -x --tb=short -q`
Expected: All tests pass (no backend changes in this sub-project)

- [ ] **Step 2: Run frontend build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Run frontend lint**

Run: `cd /home/ringuet/WorldRAG/frontend && npx next lint`
Expected: No errors

- [ ] **Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "chore: graph explorer redesign — integration fixes"
```
