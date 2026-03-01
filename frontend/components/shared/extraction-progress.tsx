"use client"

import { useState, useEffect, useCallback } from "react"
import {
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  RefreshCw,
  ChevronDown,
  ChevronUp,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { LABEL_COLORS } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { ExtractionEvent } from "@/hooks/use-extraction-progress"
import type { ChapterInfo, GraphStats, DLQEntry } from "@/lib/api/types"
import { getGraphStats } from "@/lib/api/graph"
import { getBook, getDLQ, retryDLQChapter, retryAllDLQ } from "@/lib/api/books"

interface ExtractionDashboardProps {
  bookId: string
  events: ExtractionEvent[]
  progress: number
  isConnected: boolean
  isDone: boolean
  isStarted?: boolean
  totalChapters?: number
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  pending: <Clock className="h-3.5 w-3.5 text-muted-foreground" />,
  extracting: <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />,
  extracted: <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />,
  failed: <XCircle className="h-3.5 w-3.5 text-red-400" />,
}

const ENTITY_ICONS: Record<string, string> = {
  Character: "\ud83d\udc64",
  Skill: "\u2694\ufe0f",
  Class: "\ud83d\udee1\ufe0f",
  Title: "\ud83d\udc51",
  Event: "\ud83c\udfaf",
  Location: "\ud83c\udff0",
  Item: "\ud83d\udce6",
  Creature: "\ud83d\udc32",
  Faction: "\u2694",
  Concept: "\ud83d\udca1",
}

export function ExtractionDashboard({
  bookId,
  events,
  progress,
  isConnected,
  isDone,
  isStarted = false,
  totalChapters = 0,
}: ExtractionDashboardProps) {
  const [entityStats, setEntityStats] = useState<GraphStats | null>(null)
  const [chapters, setChapters] = useState<ChapterInfo[]>([])
  const [dlqEntries, setDLQEntries] = useState<DLQEntry[]>([])
  const [showChapters, setShowChapters] = useState(false)
  const [retrying, setRetrying] = useState<number | null>(null)

  const latestEvent = events.length > 0 ? events[events.length - 1] : null
  const totalEntities = events.reduce((sum, e) => sum + e.entities_found, 0)
  const failedChapters = events.filter((e) => e.status === "failed").length
  const showWaiting = isConnected && !isStarted && events.length === 0

  // Poll for entity stats + chapter statuses during extraction
  const refreshData = useCallback(async () => {
    try {
      const [stats, bookDetail, dlq] = await Promise.all([
        getGraphStats(bookId),
        getBook(bookId),
        getDLQ(bookId).catch(() => ({ count: 0, entries: [] })),
      ])
      setEntityStats(stats)
      setChapters(bookDetail.chapters)
      setDLQEntries(dlq.entries)
    } catch {
      // silently ignore polling errors
    }
  }, [bookId])

  useEffect(() => {
    refreshData()
    if (isConnected && !isDone) {
      const interval = setInterval(refreshData, 8000)
      return () => clearInterval(interval)
    }
  }, [isConnected, isDone, refreshData])

  // Refresh once when done
  useEffect(() => {
    if (isDone) {
      refreshData()
    }
  }, [isDone, refreshData])

  const handleRetry = async (chapter: number) => {
    setRetrying(chapter)
    try {
      await retryDLQChapter(bookId, chapter)
      await refreshData()
    } finally {
      setRetrying(null)
    }
  }

  const handleRetryAll = async () => {
    setRetrying(-1)
    try {
      await retryAllDLQ()
      await refreshData()
    } finally {
      setRetrying(null)
    }
  }

  const doneChapters = chapters.filter((c) => c.status === "extracted").length
  const progressFromChapters = chapters.length > 0
    ? Math.round((doneChapters / chapters.length) * 100)
    : progress

  return (
    <div className="space-y-4">
      {/* ── Progress Bar ── */}
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          {isConnected ? (
            <Loader2 className="h-4 w-4 animate-spin text-primary shrink-0" />
          ) : isDone ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
          ) : null}

          <div className="flex-1 h-2.5 rounded-full bg-accent overflow-hidden">
            {showWaiting ? (
              <div className="h-full w-full bg-primary/30 animate-pulse rounded-full" />
            ) : (
              <div
                className={cn(
                  "h-full rounded-full transition-all duration-700",
                  isDone
                    ? failedChapters > 0 || dlqEntries.length > 0
                      ? "bg-amber-500"
                      : "bg-emerald-500"
                    : "bg-primary",
                )}
                style={{ width: `${progressFromChapters}%` }}
              />
            )}
          </div>

          <span className="text-sm font-mono text-foreground tabular-nums shrink-0 min-w-[4rem] text-right">
            {showWaiting ? "..." : `${progressFromChapters}%`}
          </span>
        </div>

        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          {showWaiting ? (
            <span>Preparing extraction pipeline...</span>
          ) : (
            <>
              <span className="font-medium text-muted-foreground">
                {doneChapters || latestEvent?.chapters_done || 0} / {chapters.length || totalChapters} chapters
              </span>
              {totalEntities > 0 && <span>{totalEntities} entities extracted</span>}
              {failedChapters > 0 && (
                <span className="flex items-center gap-1 text-red-400">
                  <XCircle className="h-3 w-3" />
                  {failedChapters} failed
                </span>
              )}
            </>
          )}
        </div>
      </div>

      {/* ── Entity Counts by Type ── */}
      {entityStats && entityStats.total_nodes > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(entityStats.nodes)
            .filter(([label, count]) => count > 0 && label in ENTITY_ICONS)
            .sort(([, a], [, b]) => b - a)
            .map(([label, count]) => {
              const plural = count > 1
                ? label === "Class" ? "es" : "s"
                : ""
              return (
                <Badge
                  key={label}
                  variant="outline"
                  className="text-xs px-2 py-0.5"
                  style={{
                    borderColor: LABEL_COLORS[label] ?? "#475569",
                    color: LABEL_COLORS[label] ?? "#94a3b8",
                  }}
                >
                  {ENTITY_ICONS[label]} {count} {label}{plural}
                </Badge>
              )
            })}
        </div>
      )}

      {/* ── Chapter Table (collapsible) ── */}
      {chapters.length > 0 && (
        <div>
          <button
            onClick={() => setShowChapters((p) => !p)}
            className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors mb-2"
          >
            {showChapters ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            Chapter Details
          </button>

          {showChapters && (
            <div className="rounded-lg border border-[var(--glass-border)] overflow-hidden max-h-[300px] overflow-y-auto">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-background z-10">
                  <tr className="text-muted-foreground uppercase tracking-wider">
                    <th className="text-left px-3 py-2 font-medium w-10">#</th>
                    <th className="text-left px-3 py-2 font-medium">Title</th>
                    <th className="text-center px-3 py-2 font-medium w-16">Status</th>
                    <th className="text-center px-3 py-2 font-medium w-20">Entities</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--glass-border)]">
                  {chapters.map((ch) => (
                    <tr
                      key={ch.number}
                      className={cn(
                        "transition-colors",
                        ch.status === "extracted"
                          ? "text-muted-foreground"
                          : ch.status === "failed"
                            ? "text-red-400/80 bg-red-500/5"
                            : "text-muted-foreground",
                      )}
                    >
                      <td className="px-3 py-1.5 font-mono">{ch.number}</td>
                      <td className="px-3 py-1.5 truncate max-w-[200px]">{ch.title || `Chapter ${ch.number}`}</td>
                      <td className="px-3 py-1.5 text-center">
                        {STATUS_ICON[ch.status] || STATUS_ICON.pending}
                      </td>
                      <td className="px-3 py-1.5 text-center font-mono">
                        {ch.entity_count > 0 ? ch.entity_count : "\u2014"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── DLQ Section ── */}
      {dlqEntries.length > 0 && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-red-400" />
              <span className="text-xs font-medium text-red-400">
                {dlqEntries.length} Failed Chapter{dlqEntries.length > 1 ? "s" : ""}
              </span>
            </div>
            {dlqEntries.length > 1 && (
              <Button
                size="sm"
                variant="ghost"
                className="h-6 text-xs text-red-400 hover:text-red-300"
                onClick={handleRetryAll}
                disabled={retrying !== null}
              >
                {retrying === -1 ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <RefreshCw className="h-3 w-3 mr-1" />}
                Retry All
              </Button>
            )}
          </div>
          <div className="space-y-1.5">
            {dlqEntries.map((entry) => (
              <div
                key={`${entry.book_id}-${entry.chapter}`}
                className="flex items-center justify-between text-xs"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-mono text-red-400/80 shrink-0">Ch. {entry.chapter}</span>
                  <span className="text-muted-foreground truncate">
                    {entry.error_type}: {entry.error_message}
                  </span>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-5 px-2 text-xs text-muted-foreground hover:text-foreground shrink-0"
                  onClick={() => handleRetry(entry.chapter)}
                  disabled={retrying !== null}
                >
                  {retrying === entry.chapter ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <RefreshCw className="h-3 w-3" />
                  )}
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// Re-export with old name for backward compatibility
export { ExtractionDashboard as ExtractionProgress }
