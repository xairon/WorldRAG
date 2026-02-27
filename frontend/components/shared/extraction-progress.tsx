"use client"

import { Loader2, CheckCircle2, XCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import type { ExtractionEvent } from "@/hooks/use-extraction-progress"

interface ExtractionProgressProps {
  events: ExtractionEvent[]
  progress: number
  isConnected: boolean
  isDone: boolean
}

export function ExtractionProgress({
  events,
  progress,
  isConnected,
  isDone,
}: ExtractionProgressProps) {
  const latestEvent = events.length > 0 ? events[events.length - 1] : null
  const totalEntities = events.reduce((sum, e) => sum + e.entities_found, 0)
  const failedChapters = events.filter((e) => e.status === "failed").length

  return (
    <div className="space-y-2">
      {/* Progress bar */}
      <div className="flex items-center gap-3">
        {isConnected ? (
          <Loader2 className="h-4 w-4 animate-spin text-indigo-400 shrink-0" />
        ) : isDone ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
        ) : null}

        <div className="flex-1 h-2 rounded-full bg-slate-800 overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-500",
              isDone
                ? failedChapters > 0
                  ? "bg-amber-500"
                  : "bg-emerald-500"
                : "bg-indigo-500",
            )}
            style={{ width: `${progress}%` }}
          />
        </div>

        <span className="text-xs text-slate-400 tabular-nums shrink-0">
          {progress}%
        </span>
      </div>

      {/* Stats */}
      {latestEvent && (
        <div className="flex items-center gap-4 text-xs text-slate-500">
          <span>
            {latestEvent.chapters_done}/{latestEvent.total} chapters
          </span>
          <span>{totalEntities} entities</span>
          {failedChapters > 0 && (
            <span className="flex items-center gap-1 text-red-400">
              <XCircle className="h-3 w-3" />
              {failedChapters} failed
            </span>
          )}
        </div>
      )}
    </div>
  )
}
