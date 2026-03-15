"use client"

import { useState, useEffect, useMemo, useCallback, useRef } from "react"
import { useParams } from "next/navigation"
import { Loader2 } from "lucide-react"
import { apiFetch } from "@/lib/api/client"
import { getSubgraph } from "@/lib/api/graph"
import { SigmaGraph } from "@/components/graph/sigma-graph"
import { GraphSearch } from "@/components/graph/graph-search"
import { GraphFilters } from "@/components/graph/graph-filters"
import { GraphBookSelector } from "@/components/graph/graph-book-selector"
import { NodeDetailPanel } from "@/components/graph/node-detail-panel"
import { GraphStatsBar } from "@/components/graph/graph-stats-bar"
import type { SubgraphData, GraphNode } from "@/lib/api/types"
import type { GraphFiltersState, EntityTypeInfo } from "@/components/graph/graph-filters"

// ── Types ──────────────────────────────────────────────────────────────────

interface BookEntry {
  id: string
  book_id: string
  original_filename: string
  status: string
}

// ── Helpers ────────────────────────────────────────────────────────────────

/** Derive unique entity types + counts from graph nodes. */
function deriveEntityTypes(nodes: GraphNode[]): EntityTypeInfo[] {
  const counts = new Map<string, number>()
  for (const node of nodes) {
    const label = node.labels?.[0] ?? "Concept"
    counts.set(label, (counts.get(label) ?? 0) + 1)
  }
  return Array.from(counts.entries())
    .map(([type, count]) => ({ type, count }))
    .sort((a, b) => b.count - a.count)
}

/** Compute max chapter from node descriptions or edge properties. */
function deriveMaxChapter(data: SubgraphData): number {
  let max = 1
  for (const edge of data.edges) {
    const ch = edge.properties?.chapter
    if (typeof ch === "number" && ch > max) max = ch
    const vf = edge.properties?.valid_from_chapter
    if (typeof vf === "number" && vf > max) max = vf
    const vt = edge.properties?.valid_to_chapter
    if (typeof vt === "number" && vt > max) max = vt
  }
  return max
}

/** Apply filters (enabled types + chapter range) to raw subgraph data. */
function applyFilters(raw: SubgraphData, filters: GraphFiltersState): SubgraphData {
  const { enabledTypes, chapterRange } = filters

  const filteredNodes = raw.nodes.filter((node) => {
    const label = node.labels?.[0] ?? "Concept"
    return enabledTypes.has(label)
  })

  const nodeIds = new Set(filteredNodes.map((n) => n.id))

  const filteredEdges = raw.edges.filter((edge) => {
    if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) return false
    const ch = edge.properties?.chapter
    if (typeof ch === "number") {
      return ch >= chapterRange[0] && ch <= chapterRange[1]
    }
    return true
  })

  return { nodes: filteredNodes, edges: filteredEdges }
}

// ── Page Component ─────────────────────────────────────────────────────────

export default function GraphExplorerPage() {
  const params = useParams<{ slug: string }>()
  const slug = params.slug

  // ── Book list state ────────────────────────────────────────────────────
  const [books, setBooks] = useState<BookEntry[]>([])
  const [booksLoading, setBooksLoading] = useState(true)
  const [selectedBookId, setSelectedBookId] = useState<string | null>(null)

  // ── Graph data state ───────────────────────────────────────────────────
  const [rawData, setRawData] = useState<SubgraphData>({ nodes: [], edges: [] })
  const [graphLoading, setGraphLoading] = useState(false)

  // ── Filter state ───────────────────────────────────────────────────────
  const [filters, setFilters] = useState<GraphFiltersState>({
    enabledTypes: new Set<string>(),
    chapterRange: [1, 1],
  })

  // ── Node detail panel state ────────────────────────────────────────────
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)

  // ── Sigma imperative handles ───────────────────────────────────────────
  const zoomInRef = useRef<() => void>(() => {})
  const zoomOutRef = useRef<() => void>(() => {})
  const fitRef = useRef<() => void>(() => {})
  const focusNodeRef = useRef<(nodeId: string) => void>(() => {})
  const [highlightNodeId, setHighlightNodeId] = useState<string | null>(null)

  // ── Fetch books for the project ────────────────────────────────────────
  useEffect(() => {
    let cancelled = false
    setBooksLoading(true)
    apiFetch<BookEntry[]>(`/projects/${slug}/books`)
      .then((data) => {
        if (cancelled) return
        // Only show books that have been extracted (have graph data)
        const extractedBooks = data.filter(
          (b) => b.status === "extracted" || b.status === "embedded",
        )
        setBooks(extractedBooks)
        if (extractedBooks.length > 0 && !selectedBookId) {
          setSelectedBookId(extractedBooks[0].book_id ?? extractedBooks[0].id)
        }
        setBooksLoading(false)
      })
      .catch(() => {
        if (!cancelled) {
          setBooks([])
          setBooksLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [slug]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Fetch subgraph when selected book changes ─────────────────────────
  useEffect(() => {
    if (!selectedBookId) return
    let cancelled = false
    setGraphLoading(true)
    setSelectedNode(null)
    setDetailOpen(false)

    getSubgraph(selectedBookId)
      .then((data) => {
        if (cancelled) return
        setRawData(data)

        // Initialize filters with all types enabled and full chapter range
        const types = deriveEntityTypes(data.nodes)
        const maxCh = deriveMaxChapter(data)
        setFilters({
          enabledTypes: new Set(types.map((t) => t.type)),
          chapterRange: [1, maxCh],
        })

        setGraphLoading(false)
      })
      .catch(() => {
        if (!cancelled) {
          setRawData({ nodes: [], edges: [] })
          setGraphLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [selectedBookId])

  // ── Derived values ─────────────────────────────────────────────────────
  const availableTypes = useMemo(() => deriveEntityTypes(rawData.nodes), [rawData])
  const maxChapter = useMemo(() => deriveMaxChapter(rawData), [rawData])
  const filteredData = useMemo(() => applyFilters(rawData, filters), [rawData, filters])

  // ── Book selector options ──────────────────────────────────────────────
  const bookOptions = useMemo(
    () =>
      books.map((b) => ({
        id: b.book_id ?? b.id,
        title: b.original_filename?.replace(/\.(epub|pdf|txt)$/i, "") ?? "Untitled",
      })),
    [books],
  )

  // ── Callbacks ──────────────────────────────────────────────────────────
  const handleNodeClick = useCallback(
    (nodeId: string, name: string, labels: string[]) => {
      const node = rawData.nodes.find((n) => n.id === nodeId)
      if (node) {
        setSelectedNode(node)
        setDetailOpen(true)
      }
    },
    [rawData],
  )

  const handleCanvasDoubleClick = useCallback(() => {
    setDetailOpen(false)
    setSelectedNode(null)
  }, [])

  const handleSearchSelect = useCallback((nodeId: string) => {
    setHighlightNodeId(nodeId)
    focusNodeRef.current(nodeId)
  }, [])

  const handleBookSelect = useCallback((bookId: string) => {
    setSelectedBookId(bookId)
  }, [])

  // ── Empty states ───────────────────────────────────────────────────────
  if (booksLoading) {
    return (
      <div className="h-[calc(100vh-48px)] flex items-center justify-center">
        <div className="flex items-center gap-3 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span className="text-sm">Loading books...</span>
        </div>
      </div>
    )
  }

  if (books.length === 0) {
    return (
      <div className="h-[calc(100vh-48px)] flex items-center justify-center">
        <div className="text-center space-y-2">
          <p className="text-sm text-muted-foreground">
            No extracted books found in this project.
          </p>
          <p className="text-xs text-muted-foreground/60">
            Upload and extract a book first to explore its knowledge graph.
          </p>
        </div>
      </div>
    )
  }

  const isEmpty = !graphLoading && filteredData.nodes.length === 0

  // ── Render ─────────────────────────────────────────────────────────────
  return (
    <div className="relative h-[calc(100vh-48px)]" onDoubleClick={handleCanvasDoubleClick}>
      {/* Sigma graph — full bleed */}
      <SigmaGraph
        data={filteredData}
        onNodeClick={handleNodeClick}
        onZoomIn={(fn) => {
          zoomInRef.current = fn
        }}
        onZoomOut={(fn) => {
          zoomOutRef.current = fn
        }}
        onFit={(fn) => {
          fitRef.current = fn
        }}
        onFocusNode={(fn) => {
          focusNodeRef.current = fn
        }}
        highlightNodeId={highlightNodeId}
        className="absolute inset-0"
      />

      {/* Loading overlay */}
      {graphLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/50 backdrop-blur-sm z-30">
          <div className="flex items-center gap-3 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span className="text-sm">Loading graph...</span>
          </div>
        </div>
      )}

      {/* Empty after filter */}
      {isEmpty && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10">
          <p className="text-sm text-muted-foreground bg-background/80 backdrop-blur-sm rounded-lg px-4 py-3 border border-border/50">
            No entities match the current filters.
          </p>
        </div>
      )}

      {/* Search — top-left */}
      <div className="absolute top-3 left-3 z-20">
        <GraphSearch bookId={selectedBookId ?? undefined} onSelect={handleSearchSelect} />
      </div>

      {/* Book selector — top-right */}
      {bookOptions.length > 1 && (
        <div className="absolute top-3 right-3 z-20">
          <GraphBookSelector
            books={bookOptions}
            selected={selectedBookId ?? ""}
            onSelect={handleBookSelect}
          />
        </div>
      )}

      {/* Filters — left, below search */}
      <div className="absolute top-14 left-3 z-20">
        <GraphFilters
          availableTypes={availableTypes}
          maxChapter={maxChapter}
          filters={filters}
          onChange={setFilters}
        />
      </div>

      {/* Node detail panel — right */}
      {selectedNode && (
        <NodeDetailPanel
          node={selectedNode}
          edges={rawData.edges}
          bookId={selectedBookId ?? undefined}
          open={detailOpen}
          onClose={() => {
            setDetailOpen(false)
            setSelectedNode(null)
          }}
        />
      )}

      {/* Stats bar — bottom-center */}
      <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-20">
        <GraphStatsBar
          nodeCount={filteredData.nodes.length}
          edgeCount={filteredData.edges.length}
          onZoomIn={() => zoomInRef.current()}
          onZoomOut={() => zoomOutRef.current()}
          onZoomFit={() => fitRef.current()}
        />
      </div>
    </div>
  )
}
