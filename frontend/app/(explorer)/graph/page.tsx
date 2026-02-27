"use client"

import { useEffect, useCallback, Suspense, useRef } from "react"
import dynamic from "next/dynamic"
import { useSearchParams } from "next/navigation"
import { Search, Loader2 } from "lucide-react"
import { getSubgraph, searchEntities, getCharacterProfile } from "@/lib/api/graph"
import { listBooks } from "@/lib/api/books"
import type { GraphNode, BookInfo } from "@/lib/api/types"
import { useBookStore } from "@/stores/book-store"
import { useGraphStore } from "@/stores/graph-store"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { GraphControls } from "@/components/graph/graph-controls"
import { NodeDetailPanel } from "@/components/graph/node-detail-panel"
import { Skeleton } from "@/components/ui/skeleton"
import { useState } from "react"

// Dynamic import for SigmaGraph (no SSR — WebGL)
const SigmaGraph = dynamic(
  () => import("@/components/graph/sigma-graph").then((m) => ({ default: m.SigmaGraph })),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center rounded-xl border border-slate-800 bg-slate-900/30" style={{ height: 650 }}>
        <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
      </div>
    ),
  },
)

function GraphExplorerContent() {
  const searchParams = useSearchParams()
  const initialBookId = searchParams.get("book_id") ?? ""
  const initialLabel = searchParams.get("label") ?? ""

  const { selectedBookId, book, chapters } = useBookStore()
  const {
    graphData,
    filters,
    selectedNode,
    loading,
    setGraphData,
    setFilters,
    setSelectedNode,
    setLoading,
  } = useGraphStore()

  const [books, setBooks] = useState<BookInfo[]>([])
  const [bookId, setBookId] = useState(initialBookId || selectedBookId || "")
  const [searchQuery, setSearchQuery] = useState("")
  const [searchResults, setSearchResults] = useState<GraphNode[]>([])
  const [highlightNodeId, setHighlightNodeId] = useState<string | null>(null)
  const sigmaRef = useRef<{ zoomIn: () => void; zoomOut: () => void; resetZoom: () => void } | null>(null)

  // Init label filter from URL
  useEffect(() => {
    if (initialLabel) {
      setFilters({ labels: [initialLabel] })
    }
  }, [initialLabel, setFilters])

  useEffect(() => {
    listBooks().then(setBooks).catch(() => {})
  }, [])

  // Sync with global book store
  useEffect(() => {
    if (selectedBookId && !initialBookId) setBookId(selectedBookId)
  }, [selectedBookId, initialBookId])

  // Fetch graph data when filters change
  const loadGraph = useCallback(async () => {
    if (!bookId) return
    setLoading(true)
    try {
      const labelParam = filters.labels.length === 1 ? filters.labels[0] : undefined
      const chapterParam = filters.chapterRange ? filters.chapterRange[1] : undefined
      const data = await getSubgraph(bookId, labelParam, chapterParam)

      // Client-side filter by multiple labels
      if (filters.labels.length > 1) {
        const filtered = {
          nodes: data.nodes.filter((n) =>
            n.labels?.some((l) => filters.labels.includes(l)),
          ),
          edges: data.edges,
        }
        const nodeIds = new Set(filtered.nodes.map((n) => n.id))
        filtered.edges = data.edges.filter(
          (e) => nodeIds.has(e.source) && nodeIds.has(e.target),
        )
        setGraphData(filtered)
      } else {
        setGraphData(data)
      }
    } catch {
      setGraphData({ nodes: [], edges: [] })
    } finally {
      setLoading(false)
    }
  }, [bookId, filters.labels, filters.chapterRange, setGraphData, setLoading])

  useEffect(() => {
    loadGraph()
  }, [loadGraph])

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    if (!searchQuery.trim()) return
    try {
      const results = await searchEntities(searchQuery, undefined, bookId || undefined)
      setSearchResults(results)
    } catch {
      setSearchResults([])
    }
  }

  const handleNodeClick = useCallback((nodeId: string, name: string, labels: string[]) => {
    const node: GraphNode = {
      id: nodeId,
      name,
      labels,
    }
    setSelectedNode(node)
  }, [setSelectedNode])

  function handleSearchResultClick(node: GraphNode) {
    setSelectedNode(node)
    setHighlightNodeId(node.id)
    setSearchResults([])
  }

  // Zoom controls
  function zoomIn() { sigmaRef.current?.zoomIn() }
  function zoomOut() { sigmaRef.current?.zoomOut() }
  function resetZoom() { sigmaRef.current?.resetZoom() }

  const totalChapters = chapters.length || book?.total_chapters || 0

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Graph Explorer</h1>
          <p className="text-slate-400 text-sm mt-1">
            {graphData.nodes.length} nodes, {graphData.edges.length} edges
          </p>
        </div>
        {loading && <Loader2 className="h-5 w-5 animate-spin text-indigo-400" />}
      </div>

      {/* Toolbar: book selector + search */}
      <div className="flex flex-wrap gap-3 items-center">
        <select
          aria-label="Select book"
          value={bookId}
          onChange={(e) => setBookId(e.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
        >
          <option value="">All books</option>
          {books.map((b) => (
            <option key={b.id} value={b.id}>{b.title}</option>
          ))}
        </select>

        <form onSubmit={handleSearch} className="flex gap-2 flex-1 max-w-md">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search entities..."
              className="pl-9"
            />
          </div>
          <Button type="submit" size="icon" variant="secondary">
            <Search className="h-4 w-4" />
          </Button>
        </form>
      </div>

      {/* Search results dropdown */}
      {searchResults.length > 0 && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-3 max-h-48 overflow-y-auto">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-slate-500">{searchResults.length} results</span>
            <button onClick={() => setSearchResults([])} className="text-slate-600 hover:text-slate-400">
              <span className="text-xs">Clear</span>
            </button>
          </div>
          <div className="space-y-0.5">
            {searchResults.map((r) => (
              <button
                key={r.id}
                onClick={() => handleSearchResultClick(r)}
                className="w-full text-left rounded-lg px-2 py-1.5 text-xs hover:bg-slate-800 transition-colors flex items-center gap-2"
              >
                <span className="truncate font-medium">{r.name}</span>
                <span className="text-slate-600 ml-auto text-[10px]">{r.labels?.[0]}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Main content: Controls + Graph + Detail panel */}
      <div className="flex gap-4">
        {/* Left: Controls */}
        <div className="w-56 shrink-0 hidden lg:block">
          <GraphControls
            totalChapters={totalChapters}
            onZoomIn={zoomIn}
            onZoomOut={zoomOut}
            onResetZoom={resetZoom}
          />
        </div>

        {/* Center: Graph */}
        <div className="flex-1 min-w-0">
          {graphData.nodes.length === 0 && !loading ? (
            <div
              className="flex items-center justify-center rounded-xl border border-dashed border-slate-700 bg-slate-900/30"
              style={{ height: 650 }}
            >
              <p className="text-slate-500 text-sm">
                {bookId ? "No entities found. Try running extraction first." : "Select a book to explore its knowledge graph."}
              </p>
            </div>
          ) : (
            <SigmaGraph
              data={graphData}
              onNodeClick={handleNodeClick}
              onReady={(actions) => { sigmaRef.current = actions }}
              highlightNodeId={highlightNodeId}
              height={650}
            />
          )}
        </div>

        {/* Right: Detail panel */}
        {selectedNode && (
          <div className="w-80 shrink-0 hidden md:block">
            <NodeDetailPanel
              node={selectedNode}
              bookId={bookId || undefined}
              onClose={() => setSelectedNode(null)}
            />
          </div>
        )}
      </div>
    </div>
  )
}

export default function GraphPage() {
  return (
    <Suspense
      fallback={
        <div className="space-y-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-[650px] rounded-xl" />
        </div>
      }
    >
      <GraphExplorerContent />
    </Suspense>
  )
}
