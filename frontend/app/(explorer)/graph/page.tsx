"use client"

import { useEffect, useCallback, Suspense, useRef, useState } from "react"
import dynamic from "next/dynamic"
import { useSearchParams } from "next/navigation"
import { motion, AnimatePresence } from "motion/react"
import { Search, Loader2, ZoomIn, ZoomOut, Maximize2 } from "lucide-react"
import { getSubgraph, searchEntities } from "@/lib/api/graph"
import { listBooks } from "@/lib/api/books"
import type { GraphNode, BookInfo } from "@/lib/api/types"
import { useBookStore } from "@/stores/book-store"
import { useGraphStore } from "@/stores/graph-store"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { GraphControls } from "@/components/graph/graph-controls"
import { NodeDetailPanel } from "@/components/graph/node-detail-panel"
import { Skeleton } from "@/components/ui/skeleton"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

// Dynamic import for SigmaGraph (no SSR - WebGL)
const SigmaGraph = dynamic(
  () => import("@/components/graph/sigma-graph").then((m) => ({ default: m.SigmaGraph })),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full w-full items-center justify-center glass rounded-2xl">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    ),
  },
)

// Stagger animation variants
const floatingPanelVariants = {
  hidden: { opacity: 0, y: 12, scale: 0.97 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      delay: i * 0.08,
      duration: 0.4,
      ease: [0.25, 0.4, 0.25, 1] as const,
    },
  }),
}

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
  const hasData = graphData.nodes.length > 0

  return (
    <div className="-m-6 lg:-m-8 relative h-[calc(100vh-3.5rem)] overflow-hidden">
      {/* Graph canvas - full bleed */}
      {hasData ? (
        <SigmaGraph
          data={graphData}
          onNodeClick={handleNodeClick}
          onReady={(actions) => { sigmaRef.current = actions }}
          highlightNodeId={highlightNodeId}
          height="100%"
        />
      ) : !loading ? (
        /* Empty state - centered glass card */
        <div className="flex h-full w-full items-center justify-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4, ease: [0.25, 0.4, 0.25, 1] as const }}
            className="glass rounded-2xl px-8 py-10 text-center max-w-sm"
          >
            <p className="text-muted-foreground text-sm">
              {bookId ? "No entities found. Try running extraction first." : "Select a book to explore its knowledge graph."}
            </p>
          </motion.div>
        </div>
      ) : (
        /* Loading state */
        <div className="flex h-full w-full items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      )}

      {/* Floating glass header bar - book selector + search + stats */}
      <motion.div
        custom={0}
        variants={floatingPanelVariants}
        initial="hidden"
        animate="visible"
        className="absolute left-4 right-4 top-4 z-20 flex flex-wrap items-center gap-3 glass rounded-2xl px-4 py-3"
      >
        <select
          aria-label="Select book"
          value={bookId}
          onChange={(e) => setBookId(e.target.value)}
          className="glass rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        >
          <option value="">All books</option>
          {books.map((b) => (
            <option key={b.id} value={b.id}>{b.title}</option>
          ))}
        </select>

        <form onSubmit={handleSearch} className="relative flex gap-2 flex-1 max-w-md">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
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

        {/* Stats + loading indicator */}
        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs text-muted-foreground hidden sm:inline">
            {graphData.nodes.length} nodes, {graphData.edges.length} edges
          </span>
          {loading && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
        </div>
      </motion.div>

      {/* Search results dropdown - floating below header */}
      <AnimatePresence>
        {searchResults.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
            className="absolute left-4 right-4 top-[4.5rem] z-30 glass rounded-2xl p-3 max-h-48 overflow-y-auto"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-muted-foreground">{searchResults.length} results</span>
              <button onClick={() => setSearchResults([])} className="text-muted-foreground hover:text-foreground">
                <span className="text-xs">Clear</span>
              </button>
            </div>
            <div className="space-y-0.5">
              {searchResults.map((r) => (
                <button
                  key={r.id}
                  onClick={() => handleSearchResultClick(r)}
                  className="w-full text-left rounded-lg px-2 py-1.5 text-xs hover:bg-[var(--glass-bg-hover)] transition-colors flex items-center gap-2"
                >
                  <span className="truncate font-medium text-foreground">{r.name}</span>
                  <span className="text-muted-foreground ml-auto text-[10px]">{r.labels?.[0]}</span>
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Floating left filter panel */}
      <motion.div
        custom={1}
        variants={floatingPanelVariants}
        initial="hidden"
        animate="visible"
        className="absolute left-4 top-20 z-10 w-56 hidden lg:block"
      >
        <GraphControls totalChapters={totalChapters} />
      </motion.div>

      {/* Floating detail panel - right side slide-in */}
      <AnimatePresence>
        {selectedNode && (
          <motion.div
            key="detail-panel"
            initial={{ x: 320, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 320, opacity: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="absolute right-0 top-0 h-full z-20 w-80 hidden md:block"
          >
            <NodeDetailPanel
              node={selectedNode}
              bookId={bookId || undefined}
              onClose={() => setSelectedNode(null)}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Floating zoom controls - bottom center pill */}
      <motion.div
        custom={2}
        variants={floatingPanelVariants}
        initial="hidden"
        animate="visible"
        className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 glass rounded-full px-2 py-1.5 flex items-center gap-1"
      >
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full text-muted-foreground hover:text-foreground" onClick={zoomIn}>
              <ZoomIn className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Zoom in</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full text-muted-foreground hover:text-foreground" onClick={zoomOut}>
              <ZoomOut className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Zoom out</TooltipContent>
        </Tooltip>
        <div className="w-px h-4 bg-[var(--glass-border)]" />
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8 rounded-full text-muted-foreground hover:text-foreground" onClick={resetZoom}>
              <Maximize2 className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Fit to screen</TooltipContent>
        </Tooltip>
      </motion.div>
    </div>
  )
}

export default function GraphPage() {
  return (
    <Suspense
      fallback={
        <div className="-m-6 lg:-m-8 h-[calc(100vh-3.5rem)] flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      }
    >
      <GraphExplorerContent />
    </Suspense>
  )
}
