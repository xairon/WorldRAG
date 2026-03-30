"use client"

import { Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { useDeleteRelation } from "@/hooks/use-graph-mutations"
import type { GraphEdge, GraphNode } from "@/lib/api/types"

interface RelationReviewTableProps {
  edges: GraphEdge[]
  nodes: GraphNode[]
}

export function RelationReviewTable({ edges, nodes }: RelationReviewTableProps) {
  const deleteMutation = useDeleteRelation()

  const nameMap = new Map(nodes.map((n) => [n.id, n.name]))

  const handleDelete = (id: string) => {
    if (confirm("Delete this relationship?")) {
      deleteMutation.mutate(id)
    }
  }

  return (
    <div className="border rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="text-left p-2 font-medium">Source</th>
            <th className="text-left p-2 font-medium">Type</th>
            <th className="text-left p-2 font-medium">Target</th>
            <th className="w-10 p-2" />
          </tr>
        </thead>
        <tbody>
          {edges.map((edge) => (
            <tr key={edge.id} className="border-b last:border-0 hover:bg-muted/30">
              <td className="p-2 font-medium">{nameMap.get(edge.source) ?? edge.source}</td>
              <td className="p-2">
                <Badge variant="outline" className="text-xs font-mono">
                  {edge.type}
                </Badge>
              </td>
              <td className="p-2 font-medium">{nameMap.get(edge.target) ?? edge.target}</td>
              <td className="p-2">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 text-destructive"
                  onClick={() => handleDelete(edge.id)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
