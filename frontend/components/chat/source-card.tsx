"use client"

import { useState } from "react"
import { BookOpen, ChevronDown } from "lucide-react"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { EntityBadge } from "@/components/shared/entity-badge"
import { cn } from "@/lib/utils"
import type { SourceChunk, RelatedEntity } from "@/lib/api/types"

interface SourceCardProps {
  sources: SourceChunk[]
  relatedEntities?: RelatedEntity[]
}

export function SourceCard({ sources, relatedEntities }: SourceCardProps) {
  const [isOpen, setIsOpen] = useState(false)

  if (sources.length === 0) return null

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger className="flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 transition-colors mt-2 group">
        <BookOpen className="h-3 w-3" />
        <span>
          {isOpen ? "Hide" : "Show"} {sources.length} source{sources.length > 1 ? "s" : ""}
        </span>
        <ChevronDown
          className={cn(
            "h-3 w-3 transition-transform",
            isOpen && "rotate-180",
          )}
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-2 space-y-2">
        {sources.map((src, i) => (
          <div
            key={i}
            className="rounded-lg bg-slate-900/60 border border-slate-800 px-3 py-2.5 text-xs"
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-indigo-400 font-medium">
                Chapter {src.chapter_number}
                {src.chapter_title ? ` — ${src.chapter_title}` : ""}
              </span>
              <span className="text-slate-600 tabular-nums">
                {(src.relevance_score * 100).toFixed(0)}% match
              </span>
            </div>
            <p className="text-slate-400 leading-relaxed line-clamp-3">
              {src.text}
            </p>
          </div>
        ))}

        {relatedEntities && relatedEntities.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {relatedEntities.map((e, i) => (
              <EntityBadge key={i} name={e.name} type={e.label} size="sm" />
            ))}
          </div>
        )}
      </CollapsibleContent>
    </Collapsible>
  )
}
