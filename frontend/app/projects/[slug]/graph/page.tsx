"use client"

import { useEffect, useState, useCallback, useRef } from "react"
import { useParams } from "next/navigation"
import dynamic from "next/dynamic"
import { AnimatePresence, motion } from "motion/react"
import { Search, Loader2, ZoomIn, ZoomOut, Maximize2 } from "lucide-react"
import { getSubgraph, searchEntities } from "@/lib/api/graph"
import { listProjectBooks } from "@/lib/api/projects"
import type { GraphNode } from "@/lib/api/types"
import { useGraphStore } from "@/stores/graph-store"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { NodeDetailPanel } from "@/components/graph/node-detail-panel"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

const SigmaGraph = dynamic(
  () => import("@/components/graph/sigma-graph").then((m) => ({ default: m.SigmaGraph })),
  { ssr: false, loading: () => <div className="flex h-full items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div> },
)

export default function ProjectGraphPage() {
  const params = useParams<{ slug: string }>()
  const { graphData, filters, selectedNode, loading, setGraphData, setSelectedNode, setLoading } = useGraphStore()

  const [bookId, setBookId] = useState("")
  const [searchQuery, setSearchQuery] = useState("")
  const [searchResults, setSearchResults] = useState<GraphNode[]>([])
  const [highlightNodeId, setHighlightNodeId] = useState<string | null>(null)
  const sigmaRef = useRef<{ zoomIn: () => void; zoomOut: () => void; resetZoom: () => void } | null>(null)

  useEffect(() => {
    listProjectBooks(params.slug)
      .then((books) => {
        const withBookId = books.find((b) => b.book_id)
        if (withBookId?.book_id) setBookId(withBookId.book_id)
      })
      .catch(() => {})
  }, [params.slug])

  const loadGraph = useCallback(async () => {
    if (!bookId) return
    setLoading(true)
    try {
      const data = await getSubgraph(bookId)
      setGraphData(data)
    } catch {
      setGraphData({ nodes: [], edges: [] })
    } finally {
      setLoading(false)
    }
  }, [bookId, setGraphData, setLoading])

  useEffect(() => { loadGraph() }, [loadGraph])

  const handleNodeClick = useCallback((nodeId: string, name: string, labels: string[]) => {
    setSelectedNode({ id: nodeId, name, labels })
  }, [setSelectedNode])

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    if (!searchQuery.trim()) return
    try {
      setSearchResults(await searchEntities(searchQuery, undefined, bookId || undefined))
    } catch { setSearchResults([]) }
  }

  const hasData = graphData.nodes.length > 0

  return (
    <div className="relative h-[600px] rounded-lg overflow-hidden border bg-background/50">
      {hasData ? (
        <SigmaGraph
          data={graphData}
          onNodeClick={handleNodeClick}
          onReady={(actions) => { sigmaRef.current = actions }}
          highlightNodeId={highlightNodeId}
          height="100%"
        />
      ) : !loading ? (
        <div className="flex h-full items-center justify-center">
          <p className="text-muted-foreground text-sm">
            {bookId ? "No entities found. Run extraction first." : "No books extracted yet."}
          </p>
        </div>
      ) : (
        <div className="flex h-full items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      )}

      {/* Search */}
      <div className="absolute left-3 right-3 top-3 z-20 flex gap-2">
        <form onSubmit={handleSearch} className="flex gap-2 flex-1 max-w-md">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="Search entities..." className="pl-9 bg-background/80 backdrop-blur" />
          </div>
        </form>
        <span className="text-xs text-muted-foreground self-center ml-auto">
          {graphData.nodes.length} nodes, {graphData.edges.length} edges
        </span>
      </div>

      <AnimatePresence>
        {searchResults.length > 0 && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="absolute left-3 right-3 top-14 z-30 bg-background/95 backdrop-blur rounded-lg border p-2 max-h-40 overflow-y-auto">
            {searchResults.map((r) => (
              <button key={r.id} onClick={() => { setSelectedNode(r); setHighlightNodeId(r.id); setSearchResults([]) }} className="w-full text-left px-2 py-1 text-xs hover:bg-muted rounded flex justify-between">
                <span className="font-medium">{r.name}</span>
                <span className="text-muted-foreground">{r.labels?.[0]}</span>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {selectedNode && (
          <motion.div initial={{ x: 300, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 300, opacity: 0 }} className="absolute right-0 top-0 h-full z-20 w-72">
            <NodeDetailPanel node={selectedNode} bookId={bookId || undefined} onClose={() => setSelectedNode(null)} />
          </motion.div>
        )}
      </AnimatePresence>

      <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-10 bg-background/80 backdrop-blur rounded-full px-2 py-1 flex gap-1 border">
        <Tooltip><TooltipTrigger asChild><Button variant="ghost" size="icon" className="h-7 w-7 rounded-full" onClick={() => sigmaRef.current?.zoomIn()}><ZoomIn className="h-3.5 w-3.5" /></Button></TooltipTrigger><TooltipContent>Zoom in</TooltipContent></Tooltip>
        <Tooltip><TooltipTrigger asChild><Button variant="ghost" size="icon" className="h-7 w-7 rounded-full" onClick={() => sigmaRef.current?.zoomOut()}><ZoomOut className="h-3.5 w-3.5" /></Button></TooltipTrigger><TooltipContent>Zoom out</TooltipContent></Tooltip>
        <Tooltip><TooltipTrigger asChild><Button variant="ghost" size="icon" className="h-7 w-7 rounded-full" onClick={() => sigmaRef.current?.resetZoom()}><Maximize2 className="h-3.5 w-3.5" /></Button></TooltipTrigger><TooltipContent>Fit</TooltipContent></Tooltip>
      </div>
    </div>
  )
}
