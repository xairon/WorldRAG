"use client"

import { Check, X, Clock, Loader2, RotateCcw, ChevronDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import type { ChapterProgress } from "@/hooks/use-extraction"
import type { ChapterInfo } from "@/lib/api/types"
import { cn } from "@/lib/utils"

interface ChapterProgressListProps {
  chapters: ChapterInfo[]
  progress: Map<number, ChapterProgress>
  onRetry: (chapter: number) => void
}

const STATUS_ICON = {
  pending: Clock,
  extracting: Loader2,
  done: Check,
  failed: X,
}

export function ChapterProgressList({ chapters, progress, onRetry }: ChapterProgressListProps) {
  return (
    <div className="space-y-1">
      {chapters.map((ch) => {
        const p = progress.get(ch.number)
        const status = p?.status ?? "pending"
        const Icon = STATUS_ICON[status]

        return (
          <Collapsible key={ch.number}>
            <div
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                status === "extracting" && "bg-primary/5",
                status === "failed" && "bg-destructive/5",
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 shrink-0",
                  status === "done" && "text-emerald-500",
                  status === "failed" && "text-destructive",
                  status === "extracting" && "text-primary animate-spin",
                  status === "pending" && "text-muted-foreground",
                )}
              />
              <span className="flex-1 truncate">
                <span className="font-mono text-xs text-muted-foreground mr-2">
                  {String(ch.number).padStart(2, "0")}
                </span>
                {ch.title || `Chapter ${ch.number}`}
              </span>

              {p?.entities != null && p.entities > 0 && (
                <Badge variant="secondary" className="text-xs">
                  {p.entities}
                </Badge>
              )}

              {status === "failed" && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={() => onRetry(ch.number)}
                >
                  <RotateCcw className="h-3 w-3" />
                </Button>
              )}

              {status === "done" && (
                <CollapsibleTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-6 w-6">
                    <ChevronDown className="h-3 w-3" />
                  </Button>
                </CollapsibleTrigger>
              )}
            </div>

            <CollapsibleContent>
              <div className="ml-10 px-3 py-2 text-xs text-muted-foreground">
                {p?.entities ?? 0} entities extracted
                {p?.duration_ms != null && ` \u00b7 ${(p.duration_ms / 1000).toFixed(1)}s`}
                {p?.error && (
                  <span className="text-destructive ml-2">{p.error}</span>
                )}
              </div>
            </CollapsibleContent>
          </Collapsible>
        )
      })}
    </div>
  )
}
