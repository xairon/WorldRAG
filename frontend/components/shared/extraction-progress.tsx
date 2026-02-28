"use client"

import { Loader2, CheckCircle2, XCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import type { ExtractionEvent } from "@/hooks/use-extraction-progress"

interface ExtractionProgressProps {
  events: ExtractionEvent[]
  progress: number
  isConnected: boolean
  isDone: boolean
  isStarted?: boolean
  totalChapters?: number
}

export function ExtractionProgress({
  events,
  progress,
  isConnected,
  isDone,
  isStarted = false,
  totalChapters = 0,
}: ExtractionProgressProps) {
  const latestEvent = events.length > 0 ? events[events.length - 1] : null
  const totalEntities = events.reduce((sum, e) => sum + e.entities_found, 0)
  const failedChapters = events.filter((e) => e.status === "failed").length

  const showWaiting = isConnected && !isStarted && events.length === 0

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
          {showWaiting ? (
            <div className="h-full w-full bg-indigo-500/30 animate-pulse rounded-full" />
          ) : (
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
          )}
        </div>

        <span className="text-xs text-slate-400 tabular-nums shrink-0">
          {showWaiting ? "..." : `${progress}%`}
        </span>
      </div>

      {/* Stats */}
      {showWaiting ? (
        <div className="text-xs text-slate-500">
          Preparing extraction pipeline...
        </div>
      ) : isStarted && !latestEvent ? (
        <div className="text-xs text-slate-500">
          Processing chapter 1/{totalChapters}...
        </div>
      ) : latestEvent ? (
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
      ) : null}
    </div>
  )
}
