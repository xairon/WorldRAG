"use client"

import { useState } from "react"
import { ChevronDown, ChevronRight } from "lucide-react"
import type { SourceChunk } from "@/lib/api/types"

interface SourcePanelProps {
  chunks: SourceChunk[]
}

export function SourcePanel({ chunks }: SourcePanelProps) {
  const [open, setOpen] = useState(false)

  if (!chunks.length) return null

  return (
    <div className="mt-2 rounded-md border border-border/50 bg-muted/30">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-1 px-3 py-2 text-sm text-muted-foreground hover:text-foreground"
      >
        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        {chunks.length} source{chunks.length > 1 ? "s" : ""} used
      </button>
      {open && (
        <div className="space-y-2 px-3 pb-3">
          {chunks.map((chunk, i) => (
            <div key={i} className="rounded bg-background p-2 text-xs">
              <span className="font-medium text-primary">
                Ch.{chunk.chapter_number}
                {chunk.position != null && `, §${chunk.position}`}
              </span>
              {chunk.relevance_score != null && (
                <span className="ml-2 text-muted-foreground">
                  ({(chunk.relevance_score * 100).toFixed(0)}%)
                </span>
              )}
              <p className="mt-1 text-muted-foreground line-clamp-3">{chunk.text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
