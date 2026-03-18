"use client"

import { useEffect, useState } from "react"
import { mapBackendStatus, getEntityHex } from "@/lib/constants"
import { formatNumber } from "@/lib/utils"
import { StatusBadge } from "@/components/shared/status-badge"
import { SigmaGraph } from "@/components/graph/sigma-graph"
import type { ChapterData } from "./chapter-table"
import type { SubgraphData, GraphEdge } from "@/lib/api/types"

interface ChapterRowProps {
  chapter: ChapterData
  bookId: string
}

export function ChapterRow({ chapter, bookId }: ChapterRowProps) {
  const [expanded, setExpanded] = useState(false)
  const [graphData, setGraphData] = useState<SubgraphData | null>(null)
  const [loading, setLoading] = useState(false)
  const uiStatus = mapBackendStatus(chapter.status)
  const canExpand = uiStatus === "done" && chapter.entityCount > 0

  // Fetch chapter subgraph when expanded
  useEffect(() => {
    if (!expanded || !canExpand || graphData) return
    setLoading(true)
    fetch(`/api/graph/subgraph/${bookId}?chapter=${chapter.number}`)
      .then((res) => res.json())
      .then((data: SubgraphData) => setGraphData(data))
      .catch(() => setGraphData({ nodes: [], edges: [] }))
      .finally(() => setLoading(false))
  }, [expanded, canExpand, bookId, chapter.number, graphData])

  // Build a lookup map from node ID to node name for the relation list
  const nodeNameMap = graphData
    ? new Map(graphData.nodes.map((n) => [n.id, n.name]))
    : null

  return (
    <>
      <tr
        className={
          canExpand
            ? "border-b cursor-pointer hover:bg-muted/50 transition-colors"
            : "border-b"
        }
        onClick={() => canExpand && setExpanded((prev) => !prev)}
      >
        <td className="px-3 py-2 font-mono text-muted-foreground tabular-nums">
          {chapter.number}
        </td>
        <td className="px-3 py-2">
          <span className="flex items-center gap-2">
            {chapter.title}
            {canExpand && (
              <span className="text-xs text-muted-foreground">
                {expanded ? "\u25BC" : "\u25B6"}
              </span>
            )}
          </span>
        </td>
        <td className="px-3 py-2 text-right font-mono tabular-nums">
          {formatNumber(chapter.words)}
        </td>
        <td className="px-3 py-2 text-right font-mono tabular-nums">
          {formatNumber(chapter.entityCount)}
        </td>
        <td className="px-3 py-2">
          <StatusBadge status={uiStatus} />
        </td>
      </tr>
      {expanded && canExpand && (
        <tr className="border-b bg-muted/30">
          <td />
          <td colSpan={4} className="px-3 py-4">
            <div className="space-y-4">
              {/* Entity type badges */}
              <div>
                <h4 className="text-xs font-medium text-muted-foreground mb-2">
                  Entities
                </h4>
                <div className="flex flex-wrap gap-3">
                  {chapter.entities
                    .filter((e) => e.count > 0)
                    .map((e) => (
                      <span
                        key={e.type}
                        className="inline-flex items-center gap-1.5 text-xs"
                      >
                        <span
                          className="inline-block size-2 rounded-full shrink-0"
                          style={{ backgroundColor: getEntityHex(e.type) }}
                        />
                        <span className="text-muted-foreground">{e.type}</span>
                        <span className="font-mono tabular-nums">
                          {formatNumber(e.count)}
                        </span>
                      </span>
                    ))}
                </div>
              </div>

              {/* Relations list */}
              {graphData && graphData.edges.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground mb-2">
                    Relations ({graphData.edges.length})
                  </h4>
                  <div className="max-h-40 overflow-auto text-xs space-y-1">
                    {graphData.edges.slice(0, 30).map((edge: GraphEdge) => (
                      <div
                        key={edge.id}
                        className="flex items-center gap-1 text-muted-foreground"
                      >
                        <span className="font-medium text-foreground">
                          {nodeNameMap?.get(edge.source) ?? edge.source}
                        </span>
                        <span className="text-primary">
                          &rarr; {edge.type} &rarr;
                        </span>
                        <span className="font-medium text-foreground">
                          {nodeNameMap?.get(edge.target) ?? edge.target}
                        </span>
                      </div>
                    ))}
                    {graphData.edges.length > 30 && (
                      <div className="text-muted-foreground italic">
                        +{graphData.edges.length - 30} more
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Mini graph */}
              {loading && (
                <div className="h-[200px] flex items-center justify-center text-sm text-muted-foreground">
                  Loading graph...
                </div>
              )}
              {graphData && graphData.nodes.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-muted-foreground mb-2">
                    Knowledge Graph ({graphData.nodes.length} nodes,{" "}
                    {graphData.edges.length} edges)
                  </h4>
                  <div className="relative h-[250px] rounded-md border overflow-hidden bg-background">
                    <SigmaGraph data={graphData} />
                  </div>
                </div>
              )}
              {graphData && graphData.nodes.length === 0 && !loading && (
                <div className="text-xs text-muted-foreground italic">
                  No graph data for this chapter
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
