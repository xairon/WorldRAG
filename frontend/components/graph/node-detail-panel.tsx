"use client"

import { useState } from "react"
import Link from "next/link"
import { X, BookOpen, MessageSquare, ChevronDown, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { getEntityHex } from "@/lib/constants"
import type { GraphNode, GraphEdge } from "@/lib/api/types"

interface NodeDetailPanelProps {
  node: GraphNode
  edges: GraphEdge[]
  bookId?: string
  open: boolean
  onClose: () => void
}

export function NodeDetailPanel({ node, edges, bookId, open, onClose }: NodeDetailPanelProps) {
  const primaryLabel = node.labels?.[0] ?? "Concept"

  // Collect relations involving this node, grouped by type
  const relatedEdges = edges.filter((e) => e.source === node.id || e.target === node.id)
  const groupedRelations = new Map<string, GraphEdge[]>()
  for (const edge of relatedEdges) {
    const list = groupedRelations.get(edge.type) ?? []
    list.push(edge)
    groupedRelations.set(edge.type, list)
  }

  // Compute metadata
  const relationCount = relatedEdges.length
  const chapters = relatedEdges
    .flatMap((e) => {
      const ch = e.properties?.chapter
      return typeof ch === "number" ? [ch] : []
    })

  const firstChapter = chapters.length > 0 ? Math.min(...chapters) : undefined
  const lastChapter = chapters.length > 0 ? Math.max(...chapters) : undefined

  return (
    <div
      className={`absolute top-0 right-0 h-full w-80 border-l border-border bg-background/95 backdrop-blur-sm shadow-xl transition-transform duration-300 ease-in-out z-20 ${
        open ? "translate-x-0" : "translate-x-full"
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center gap-2.5 min-w-0 flex-1">
          <h3 className="text-xl font-semibold truncate text-foreground">{node.name}</h3>
          <span
            className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium text-white shrink-0"
            style={{ backgroundColor: getEntityHex(primaryLabel) }}
          >
            {primaryLabel}
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-muted-foreground hover:text-foreground transition-colors ml-2 shrink-0"
          aria-label="Close panel"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <ScrollArea className="h-[calc(100%-4rem)]">
        <div className="p-4 space-y-5">
          {/* Description */}
          {node.description && (
            <p className="text-sm text-muted-foreground leading-relaxed">{node.description}</p>
          )}

          {/* Metadata */}
          <div className="grid grid-cols-2 gap-3">
            {firstChapter !== undefined && (
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  First Chapter
                </span>
                <p className="text-sm font-mono text-foreground">{firstChapter}</p>
              </div>
            )}
            {lastChapter !== undefined && (
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Last Chapter
                </span>
                <p className="text-sm font-mono text-foreground">{lastChapter}</p>
              </div>
            )}
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Relations
              </span>
              <p className="text-sm font-mono text-foreground">{relationCount}</p>
            </div>
          </div>

          {/* Relations grouped by type */}
          {groupedRelations.size > 0 && (
            <div className="space-y-2">
              <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Relationships
              </h4>
              {Array.from(groupedRelations.entries()).map(([type, typeEdges]) => (
                <RelationGroup
                  key={type}
                  type={type}
                  edges={typeEdges}
                  currentNodeId={node.id}
                />
              ))}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-2 border-t border-border">
            <Button variant="outline" size="sm" className="h-8 text-xs" asChild>
              <Link
                href={
                  bookId
                    ? `/read/${bookId}?entity=${encodeURIComponent(node.name)}`
                    : `/read?entity=${encodeURIComponent(node.name)}`
                }
              >
                <BookOpen className="h-3 w-3 mr-1.5" />
                Open in Reader
              </Link>
            </Button>
            <Button variant="outline" size="sm" className="h-8 text-xs" asChild>
              <Link
                href={
                  bookId
                    ? `/chat?book=${bookId}&q=${encodeURIComponent(node.name)}`
                    : `/chat?q=${encodeURIComponent(node.name)}`
                }
              >
                <MessageSquare className="h-3 w-3 mr-1.5" />
                View in Chat
              </Link>
            </Button>
          </div>
        </div>
      </ScrollArea>
    </div>
  )
}

function RelationGroup({
  type,
  edges,
  currentNodeId,
}: {
  type: string
  edges: GraphEdge[]
  currentNodeId: string
}) {
  const [expanded, setExpanded] = useState(false)

  const displayEdges = expanded ? edges : edges.slice(0, 3)
  const hasMore = edges.length > 3

  return (
    <div className="rounded-md border border-border/50 overflow-hidden">
      <button
        onClick={() => setExpanded((prev) => !prev)}
        className="flex items-center gap-1.5 w-full px-2.5 py-1.5 text-left text-xs font-medium text-foreground hover:bg-accent/50 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
        )}
        <span className="uppercase tracking-wider">{type}</span>
        <span className="text-muted-foreground font-mono ml-auto">{edges.length}</span>
      </button>
      {(expanded || !hasMore) && (
        <div className="px-2.5 pb-2 space-y-1">
          {displayEdges.map((edge) => {
            const targetId = edge.source === currentNodeId ? edge.target : edge.source
            return (
              <div key={edge.id} className="text-xs text-muted-foreground truncate pl-4">
                {targetId}
              </div>
            )
          })}
          {expanded && hasMore && edges.length > displayEdges.length && (
            <div className="text-[10px] text-muted-foreground/60 pl-4">
              +{edges.length - displayEdges.length} more
            </div>
          )}
        </div>
      )}
    </div>
  )
}
