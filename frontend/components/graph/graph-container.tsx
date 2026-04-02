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
function deriveTypeCounts(
  graph: MultiDirectedGraph,
): Array<{ type: string; count: number }> {
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
  const [labelsParam, setLabelsParam] = useQueryState(
    "labels",
    parseAsString.withDefault(""),
  )
  const [chapterParam, setChapterParam] = useQueryState(
    "chapter",
    parseAsInteger,
  )
  const [selectedNodeId, setSelectedNodeId] = useQueryState(
    "node",
    parseAsString,
  )

  const activeLabels = useMemo(
    () => (labelsParam ? labelsParam.split(",").filter(Boolean) : []),
    [labelsParam],
  )
  const chapterFilter = chapterParam ?? null

  // Data fetching — single label for server-side, visual filtering for multi-label
  const serverLabel = activeLabels.length === 1 ? activeLabels[0] : undefined
  const {
    data: subgraphData,
    isLoading,
    error,
    refetch,
  } = useSubgraph(bookId, {
    labels: serverLabel ? [serverLabel] : undefined,
    chapter: chapterFilter ?? undefined,
  })

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
    setGraph(g) // eslint-disable-line react-hooks/set-state-in-effect
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

    setGraph(g) // eslint-disable-line react-hooks/set-state-in-effect
    setExpandNodeId(null) // eslint-disable-line react-hooks/set-state-in-effect
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
    (labels: string[]) =>
      setLabelsParam(labels.length > 0 ? labels.join(",") : ""),
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
  const typeCounts = useMemo(
    () => (graph ? deriveTypeCounts(graph) : []),
    [graph],
  )
  const availableLabels = useMemo(
    () => typeCounts.map((t) => t.type),
    [typeCounts],
  )
  const maxChapter = useMemo(
    () => (subgraphData ? deriveMaxChapter(subgraphData) : 1),
    [subgraphData],
  )

  // Apply visual label filter (hide nodes whose type isn't in activeLabels)
  // For multi-label: sigma's nodeReducer handles visibility
  // For single label: server already filtered
  const filteredGraph = useMemo(() => {
    if (!graph || activeLabels.length === 0) return graph
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
    return (
      <ErrorState
        title="Failed to load graph"
        error={error as Error}
        onRetry={() => refetch()}
      />
    )
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
