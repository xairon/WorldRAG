"use client"
import { useParams } from "next/navigation"

export default function ProjectGraphPage() {
  const params = useParams<{ slug: string }>()

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Knowledge graph for <span className="font-medium text-foreground">{params.slug}</span>
      </p>
      <div className="h-[600px] rounded-lg border bg-background/50">
        <p className="flex items-center justify-center h-full text-muted-foreground text-sm">
          Graph explorer — extract a book first to see the knowledge graph.
        </p>
      </div>
    </div>
  )
}
