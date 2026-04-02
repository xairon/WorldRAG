# Ontology Viewer Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite ontology viewer with TanStack Query, circular SVG schema graph, click-to-filter, book selector, and proper states.

**Architecture:** Single TanStack Query hook feeds data to an orchestrator that renders schema graph + tables. Click interactions on the graph filter the tables. Circular layout replaces force simulation.

**Tech Stack:** Next.js 16 / React 19 / TypeScript, TanStack Query v5, nuqs, motion, shadcn/ui, SVG

**Spec:** `docs/superpowers/specs/2026-04-02-ontology-viewer-redesign.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `frontend/hooks/use-ontology.ts` | TanStack Query hook for ontology data |
| Create | `frontend/components/ontology/ontology-page-content.tsx` | Orchestrator with book selector + layout |
| Rewrite | `frontend/components/ontology/schema-graph.tsx` | Circular layout SVG, motion, click-to-filter |
| Modify | `frontend/components/ontology/entity-type-table.tsx` | Use shared ConfidenceBar, accept selectedType filter |
| Modify | `frontend/components/ontology/relation-type-table.tsx` | Accept selectedType filter |
| Modify | `frontend/app/projects/[slug]/ontology/page.tsx` | Use new orchestrator |
| Delete | `frontend/components/ontology/ontology-dashboard.tsx` | Replaced |

---

### Task 1: Ontology TanStack Query hook

**Files:**
- Create: `frontend/hooks/use-ontology.ts`

- [ ] **Step 1: Create the hook**

```typescript
"use client"

import { useQuery } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api/client"
import type { OntologyData } from "@/lib/api/graph"

export function useOntology(bookId: string | null) {
  return useQuery({
    queryKey: ["ontology", bookId],
    queryFn: () => apiFetch<OntologyData>(`/graph/ontology/${bookId}`),
    enabled: !!bookId,
    staleTime: 5 * 60_000,
  })
}
```

- [ ] **Step 2: Verify**: `cd /home/ringuet/WorldRAG/frontend && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/hooks/use-ontology.ts
git commit -m "feat: TanStack Query hook for ontology data"
```

---

### Task 2: Schema graph rewrite — circular layout with interactions

**Files:**
- Rewrite: `frontend/components/ontology/schema-graph.tsx`

- [ ] **Step 1: Rewrite schema-graph.tsx**

Replace the entire file. Key design decisions:
- **Circular layout by layer**: core types in inner circle (radius 120), genre in middle (radius 200), induced in outer (radius 270)
- **No force simulation**: positions computed deterministically from entity count and layer
- **SVG with motion**: nodes fade in with stagger, hover dims non-connected
- **Click-to-filter**: clicking a node calls `onSelectType(label)`, clicking background clears
- **Gradient edges**: each edge gets a linearGradient from source color to target color
- **Responsive**: viewBox-based SVG that scales

```typescript
"use client"

import { useMemo, useState, useCallback } from "react"
import { motion } from "motion/react"
import { getEntityHex, ENTITY_HEX_FALLBACK } from "@/lib/constants"
import type { OntologyEntityType, OntologySchemaEdge } from "@/lib/api/graph"

interface SchemaGraphProps {
  entityTypes: OntologyEntityType[]
  schemaEdges: OntologySchemaEdge[]
  selectedType: string | null
  onSelectType: (type: string | null) => void
}

interface LayoutNode {
  id: string
  count: number
  layer: string
  x: number
  y: number
  radius: number
  color: string
}

interface LayoutEdge {
  source: string
  target: string
  relation: string
  count: number
}

const LAYER_RADII = { core: 130, genre: 220, induced: 290 } as const
const CENTER = { x: 400, y: 350 }
const NODE_MIN_R = 18
const NODE_MAX_R = 40

function computeLayout(entityTypes: OntologyEntityType[]): LayoutNode[] {
  const groups: Record<string, OntologyEntityType[]> = { core: [], genre: [], induced: [] }
  for (const et of entityTypes) {
    const layer = et.layer ?? "core"
    ;(groups[layer] ?? groups.core).push(et)
  }

  const maxCount = Math.max(1, ...entityTypes.map((e) => e.count))
  const nodes: LayoutNode[] = []

  for (const [layer, types] of Object.entries(groups)) {
    if (types.length === 0) continue
    const ringRadius = LAYER_RADII[layer as keyof typeof LAYER_RADII] ?? 220
    const angleStep = (2 * Math.PI) / types.length
    const startAngle = -Math.PI / 2 // start from top

    for (let i = 0; i < types.length; i++) {
      const et = types[i]
      const angle = startAngle + i * angleStep
      const nodeRadius =
        NODE_MIN_R + (NODE_MAX_R - NODE_MIN_R) * Math.sqrt(et.count / maxCount)

      nodes.push({
        id: et.label,
        count: et.count,
        layer,
        x: CENTER.x + ringRadius * Math.cos(angle),
        y: CENTER.y + ringRadius * Math.sin(angle),
        radius: nodeRadius,
        color: getEntityHex(et.label),
      })
    }
  }

  return nodes
}

function aggregateEdges(schemaEdges: OntologySchemaEdge[]): LayoutEdge[] {
  const map = new Map<string, LayoutEdge>()
  for (const e of schemaEdges) {
    const key = `${e.source}::${e.target}`
    const existing = map.get(key)
    if (existing) {
      existing.count += e.count
      if (!existing.relation.includes(e.relation)) {
        existing.relation += `, ${e.relation}`
      }
    } else {
      map.set(key, { source: e.source, target: e.target, relation: e.relation, count: e.count })
    }
  }
  return Array.from(map.values())
}

export function SchemaGraph({
  entityTypes,
  schemaEdges,
  selectedType,
  onSelectType,
}: SchemaGraphProps) {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)

  const nodes = useMemo(() => computeLayout(entityTypes), [entityTypes])
  const edges = useMemo(() => aggregateEdges(schemaEdges), [schemaEdges])
  const nodeMap = useMemo(
    () => new Map(nodes.map((n) => [n.id, n])),
    [nodes],
  )

  // Connected nodes for hover/select highlighting
  const connectedTo = useMemo(() => {
    const active = hoveredNode ?? selectedType
    if (!active) return null
    const set = new Set<string>([active])
    for (const e of edges) {
      if (e.source === active) set.add(e.target)
      if (e.target === active) set.add(e.source)
    }
    return set
  }, [hoveredNode, selectedType, edges])

  const getNodeOpacity = useCallback(
    (id: string) => {
      if (!connectedTo) return 1
      return connectedTo.has(id) ? 1 : 0.15
    },
    [connectedTo],
  )

  const getEdgeOpacity = useCallback(
    (source: string, target: string) => {
      const active = hoveredNode ?? selectedType
      if (!active) return 0.4
      return source === active || target === active ? 0.8 : 0.05
    },
    [hoveredNode, selectedType],
  )

  const handleNodeClick = useCallback(
    (id: string) => {
      onSelectType(selectedType === id ? null : id)
    },
    [selectedType, onSelectType],
  )

  return (
    <div className="w-full overflow-hidden rounded-xl border bg-card">
      {/* Legend header */}
      <div className="flex items-center gap-4 px-4 py-2 border-b text-xs">
        <span className="text-muted-foreground font-medium">Layers:</span>
        {[
          { layer: "core", color: "#3b82f6", label: "Core" },
          { layer: "genre", color: "#8b5cf6", label: "Genre" },
          { layer: "induced", color: "#f59e0b", label: "Induced" },
        ].map((l) => (
          <span key={l.layer} className="flex items-center gap-1.5">
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: l.color }}
            />
            {l.label}
          </span>
        ))}
        {selectedType && (
          <button
            onClick={() => onSelectType(null)}
            className="ml-auto text-xs text-muted-foreground hover:text-foreground"
          >
            Clear filter
          </button>
        )}
      </div>

      <svg
        viewBox="0 0 800 700"
        className="w-full h-auto"
        onClick={(e) => {
          if ((e.target as SVGElement).tagName === "svg") {
            onSelectType(null)
          }
        }}
      >
        <defs>
          {/* Glow filter */}
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          {/* Arrow marker */}
          <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse"
            fill="currentColor" opacity="0.4">
            <path d="M 0 0 L 10 5 L 0 10 z" />
          </marker>
          {/* Edge gradients */}
          {edges.map((edge, i) => {
            const src = nodeMap.get(edge.source)
            const tgt = nodeMap.get(edge.target)
            if (!src || !tgt) return null
            return (
              <linearGradient
                key={`grad-${i}`}
                id={`edge-grad-${i}`}
                x1={src.x} y1={src.y} x2={tgt.x} y2={tgt.y}
                gradientUnits="userSpaceOnUse"
              >
                <stop offset="0%" stopColor={src.color} stopOpacity="0.6" />
                <stop offset="100%" stopColor={tgt.color} stopOpacity="0.6" />
              </linearGradient>
            )
          })}
        </defs>

        {/* Edges */}
        {edges.map((edge, i) => {
          const src = nodeMap.get(edge.source)
          const tgt = nodeMap.get(edge.target)
          if (!src || !tgt) return null

          // Offset edge endpoints to node border
          const dx = tgt.x - src.x
          const dy = tgt.y - src.y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const nx = dx / dist
          const ny = dy / dist

          const x1 = src.x + nx * src.radius
          const y1 = src.y + ny * src.radius
          const x2 = tgt.x - nx * tgt.radius
          const y2 = tgt.y - ny * tgt.radius

          // Midpoint for label
          const mx = (x1 + x2) / 2
          const my = (y1 + y2) / 2

          const opacity = getEdgeOpacity(edge.source, edge.target)
          const label = edge.relation.length > 20
            ? edge.relation.slice(0, 18) + "\u2026"
            : edge.relation

          return (
            <g key={`edge-${i}`} opacity={opacity}>
              <line
                x1={x1} y1={y1} x2={x2} y2={y2}
                stroke={`url(#edge-grad-${i})`}
                strokeWidth={Math.max(1, Math.min(3, Math.log2(edge.count + 1)))}
                markerEnd="url(#arrow)"
              />
              <text
                x={mx} y={my - 4}
                textAnchor="middle"
                className="fill-muted-foreground"
                fontSize="8"
                opacity="0.7"
              >
                {label}
              </text>
            </g>
          )
        })}

        {/* Nodes */}
        {nodes.map((node, i) => {
          const opacity = getNodeOpacity(node.id)
          const isSelected = selectedType === node.id
          const isHovered = hoveredNode === node.id

          return (
            <motion.g
              key={node.id}
              initial={{ opacity: 0, scale: 0.5 }}
              animate={{
                opacity,
                scale: 1,
              }}
              transition={{ delay: i * 0.03, duration: 0.3 }}
              style={{ cursor: "pointer" }}
              onMouseEnter={() => setHoveredNode(node.id)}
              onMouseLeave={() => setHoveredNode(null)}
              onClick={(e) => {
                e.stopPropagation()
                handleNodeClick(node.id)
              }}
            >
              {/* Glow circle */}
              <circle
                cx={node.x} cy={node.y}
                r={node.radius + 4}
                fill={node.color}
                opacity={isSelected || isHovered ? 0.25 : 0}
                filter="url(#glow)"
              />
              {/* Main circle */}
              <circle
                cx={node.x} cy={node.y}
                r={node.radius}
                fill={node.color}
                opacity={0.15}
                stroke={node.color}
                strokeWidth={isSelected ? 3 : 1.5}
                strokeDasharray={node.layer === "induced" ? "4,3" : "none"}
              />
              {/* Label */}
              <text
                x={node.x} y={node.y - 2}
                textAnchor="middle"
                dominantBaseline="middle"
                className="fill-foreground font-medium pointer-events-none"
                fontSize={node.radius > 28 ? "11" : "9"}
              >
                {node.id}
              </text>
              {/* Count */}
              <text
                x={node.x} y={node.y + 12}
                textAnchor="middle"
                dominantBaseline="middle"
                className="fill-muted-foreground pointer-events-none"
                fontSize="8"
              >
                {node.count}
              </text>
            </motion.g>
          )
        })}
      </svg>
    </div>
  )
}
```

- [ ] **Step 2: Verify**: `cd /home/ringuet/WorldRAG/frontend && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/components/ontology/schema-graph.tsx
git commit -m "feat: schema-graph rewrite — circular layout, gradient edges, motion animations, click-to-filter"
```

---

### Task 3: Update tables to accept selectedType filter + orchestrator

**Files:**
- Modify: `frontend/components/ontology/entity-type-table.tsx`
- Modify: `frontend/components/ontology/relation-type-table.tsx`
- Create: `frontend/components/ontology/ontology-page-content.tsx`
- Modify: `frontend/app/projects/[slug]/ontology/page.tsx`
- Delete: `frontend/components/ontology/ontology-dashboard.tsx`

- [ ] **Step 1: Update entity-type-table.tsx**

Add `selectedType` prop. When set, highlight the matching row. Also replace the internal ConfidenceBar with the shared one from `@/components/ui/confidence-bar`.

Read the existing file first, then modify:
- Add `selectedType?: string | null` to props
- Import `ConfidenceBar` from `@/components/ui/confidence-bar` (already exists from sub-project 1)
- Remove the internal `ConfidenceBar` function
- Add row highlighting: if `selectedType === et.label`, apply `bg-accent` class

- [ ] **Step 2: Update relation-type-table.tsx**

Add `selectedType` prop. When set, filter to show only relations where the type appears in the endpoints.

Read the existing file first, then modify:
- Add `selectedType?: string | null` to props
- If `selectedType` is set, filter `relationTypes` to only those that appear in `schemaEdges` where source or target matches `selectedType`

- [ ] **Step 3: Create ontology-page-content.tsx**

```typescript
"use client"

import { useMemo, useState } from "react"
import { useQueryState, parseAsString } from "nuqs"
import { Loader2 } from "lucide-react"
import { useBooks } from "@/hooks/use-books"
import { useOntology } from "@/hooks/use-ontology"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ErrorState } from "@/components/ui/error-state"
import { EmptyState } from "@/components/shared/empty-state"
import { StatCards } from "./stat-cards"
import { SchemaGraph } from "./schema-graph"
import { EntityTypeTable } from "./entity-type-table"
import { RelationTypeTable } from "./relation-type-table"

interface OntologyPageContentProps {
  slug: string
}

export function OntologyPageContent({ slug }: OntologyPageContentProps) {
  const [bookParam, setBookParam] = useQueryState("book", parseAsString)
  const [selectedType, setSelectedType] = useState<string | null>(null)

  const { data: booksRaw, isLoading: booksLoading } = useBooks(slug)

  const books = useMemo(() => {
    if (!booksRaw) return []
    return (booksRaw as Array<Record<string, unknown>>)
      .filter((b) => {
        const status = b.status as string
        return ["extracted", "embedded"].includes(status)
      })
      .map((b) => ({
        id: (b.book_id as string) ?? (b.id as string) ?? "",
        title: (b.original_filename as string) ?? (b.title as string) ?? "Book",
      }))
  }, [booksRaw])

  const effectiveBookId = bookParam ?? books[0]?.id ?? null

  const {
    data: ontology,
    isLoading: ontLoading,
    error: ontError,
    refetch,
  } = useOntology(effectiveBookId)

  if (booksLoading || ontLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (books.length === 0) {
    return (
      <EmptyState
        title="No extracted books"
        description="Extract a book first to view its ontology schema."
      />
    )
  }

  if (ontError) {
    return (
      <ErrorState
        title="Failed to load ontology"
        error={ontError as Error}
        onRetry={() => refetch()}
      />
    )
  }

  if (!ontology) return null

  return (
    <div className="space-y-6">
      {/* Header with book selector */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Ontology Schema</h1>
        {books.length > 1 && (
          <Select
            value={effectiveBookId ?? ""}
            onValueChange={(v) => setBookParam(v)}
          >
            <SelectTrigger className="w-48">
              <SelectValue placeholder="Select book" />
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
      </div>

      {/* Stat cards */}
      <StatCards
        totalEntities={ontology.stats.total_entities}
        totalRelations={ontology.stats.total_relations}
        entityTypes={ontology.stats.entity_type_count}
        relationTypes={ontology.stats.relation_type_count}
      />

      {/* Schema graph */}
      <SchemaGraph
        entityTypes={ontology.entity_types}
        schemaEdges={ontology.schema_edges}
        selectedType={selectedType}
        onSelectType={setSelectedType}
      />

      {/* Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <EntityTypeTable
          entityTypes={ontology.entity_types}
          selectedType={selectedType}
        />
        <RelationTypeTable
          relationTypes={ontology.relation_types}
          schemaEdges={ontology.schema_edges}
          selectedType={selectedType}
        />
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Update page.tsx**

Replace `frontend/app/projects/[slug]/ontology/page.tsx`:

```typescript
"use client"

import { use } from "react"
import { OntologyPageContent } from "@/components/ontology/ontology-page-content"

export default function OntologyPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = use(params)
  return (
    <div className="container max-w-6xl py-8">
      <OntologyPageContent slug={slug} />
    </div>
  )
}
```

- [ ] **Step 5: Delete old dashboard**

```bash
rm frontend/components/ontology/ontology-dashboard.tsx
```

- [ ] **Step 6: Fix broken imports**

```bash
grep -r "ontology-dashboard\|OntologyDashboard" --include="*.ts" --include="*.tsx" frontend/ -l
```
Fix any remaining references.

- [ ] **Step 7: Verify build**

Run: `cd /home/ringuet/WorldRAG/frontend && npm run build`

- [ ] **Step 8: Lint**

Run: `cd /home/ringuet/WorldRAG/frontend && npx next lint`
Fix any errors.

- [ ] **Step 9: Commit**

```bash
git add -A frontend/
git commit -m "feat: ontology viewer redesign — TanStack Query, circular schema graph, click-to-filter tables"
```
