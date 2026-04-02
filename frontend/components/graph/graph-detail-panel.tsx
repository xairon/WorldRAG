"use client"

import { useMemo } from "react"
import Link from "next/link"
import {
  X,
  Expand,
  BookOpen,
  MessageSquare,
  ChevronDown,
} from "lucide-react"
import { motion, AnimatePresence } from "motion/react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
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
  bookId: _bookId,
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
      const type = (edgeAttrs.type as string) ?? "RELATES_TO"
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
      const type = (edgeAttrs.type as string) ?? "RELATES_TO"
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

  const totalRelations = relationGroups.reduce(
    (sum, g) => sum + g.relations.length,
    0,
  )

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
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0"
            onClick={onClose}
          >
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
                <Collapsible
                  key={group.type}
                  defaultOpen={group.relations.length <= 5}
                >
                  <CollapsibleTrigger className="flex items-center gap-1.5 w-full py-1 text-xs font-medium hover:text-foreground text-muted-foreground">
                    <ChevronDown className="h-3 w-3 transition-transform [[data-state=closed]>&]:rotate-[-90deg]" />
                    <span className="font-mono">{group.type}</span>
                    <span className="ml-auto text-muted-foreground">
                      ({group.relations.length})
                    </span>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <div className="ml-4 space-y-1 mt-1">
                      {group.relations.map((rel, i) => (
                        <div
                          key={`${rel.targetId}-${i}`}
                          className="flex items-center gap-1.5 text-xs"
                        >
                          <span className="text-muted-foreground">
                            {rel.direction === "out" ? "→" : "←"}
                          </span>
                          <span
                            className="h-1.5 w-1.5 rounded-full shrink-0"
                            style={{
                              backgroundColor: getEntityHex(rel.targetType),
                            }}
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
              <Link
                href={`/projects/${projectSlug}/chat?q=${encodeURIComponent(name)}`}
              >
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
