"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { AlertTriangle } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Progress } from "@/components/ui/progress"
import { ExtractionAction } from "@/components/extraction/extraction-action"
import { ExtractionHeader } from "@/components/extraction/extraction-header"
import { ExtractionDonut } from "@/components/extraction/extraction-donut"
import { ChapterTable, type ChapterData } from "@/components/extraction/chapter-table"
import { LiveFeed } from "@/components/extraction/live-feed"
import { useExtractionStream } from "@/hooks/use-extraction-stream"
import { useExtractionStore } from "@/stores/extraction-store"
import { mapBackendStatus } from "@/lib/constants"

interface BookInfo {
  id: string
  title: string
  total_chapters: number
  status: string
  total_cost_usd: number
}

interface ChapterInfo {
  number: number
  title: string
  words?: number
  word_count?: number
  entity_count?: number
  relation_count?: number
  status: string
  entities?: { type: string; count: number }[]
}

interface ExtractionDashboardProps {
  slug: string
  bookId: string
  book: BookInfo
  chapters: ChapterInfo[]
  hasProfile: boolean
  isFirstBook: boolean
}

export function ExtractionDashboard({
  slug,
  bookId,
  book,
  chapters,
  hasProfile,
  isFirstBook,
}: ExtractionDashboardProps) {
  const router = useRouter()
  const [starting, setStarting] = useState(false)
  const { connect, disconnect, status, feedMessages, errorDetail } =
    useExtractionStream(bookId)

  // ── Derived from server data (polled every 10s) ──────────────────────
  const chaptersDone = useMemo(
    () => chapters.filter((c) => c.status === "extracted").length,
    [chapters],
  )
  const chaptersTotal = book.total_chapters

  const totalEntities = useMemo(
    () => chapters.reduce((sum, ch) => sum + (ch.entity_count ?? 0), 0),
    [chapters],
  )
  const totalRelations = useMemo(
    () => chapters.reduce((sum, ch) => sum + (ch.relation_count ?? 0), 0),
    [chapters],
  )

  const chapterRows: ChapterData[] = useMemo(
    () =>
      chapters.map((ch) => ({
        number: ch.number,
        title: ch.title,
        words: ch.words ?? ch.word_count ?? 0,
        entityCount: ch.entity_count ?? 0,
        status: ch.status,
        entities: ch.entities ?? [],
      })),
    [chapters],
  )

  const donutData = useMemo(() => {
    const totals: Record<string, number> = {}
    for (const ch of chapters) {
      for (const e of ch.entities ?? []) {
        totals[e.type] = (totals[e.type] ?? 0) + e.count
      }
    }
    return Object.entries(totals).map(([type, count]) => ({ type, count }))
  }, [chapters])

  // ── Status logic ─────────────────────────────────────────────────────
  const isExtracting = book.status === "extracting"
  const isError = book.status === "failed" || book.status === "partial" || book.status === "error_quota"
  const isDone = book.status === "extracted" || book.status === "embedded"

  const effectiveStatus = isExtracting
    ? "extracting"
    : isError
      ? "error"
      : book.status

  // ── Polling: refresh server data every 10s while extracting ──────────
  useEffect(() => {
    if (!isExtracting) return
    const interval = setInterval(() => router.refresh(), 10_000)
    return () => clearInterval(interval)
  }, [isExtracting, router])

  // Auto-connect SSE when page loads during active extraction
  useEffect(() => {
    if (isExtracting && status === "idle") {
      connect()
    }
  }, [isExtracting, status, connect])

  // Refresh once when extraction completes (detected via SSE "done" or status change)
  useEffect(() => {
    if (status === "done" || (isDone && status !== "idle")) {
      router.refresh()
    }
  }, [status, isDone, router])

  // ── Handlers ─────────────────────────────────────────────────────────
  const extractUrl = `/api/books/${bookId}/extract/v4`

  const handleStart = useCallback(async () => {
    setStarting(true)
    useExtractionStore.getState().reset()
    try {
      const res = await fetch(extractUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      })
      if (!res.ok) throw new Error(`Extract failed: ${res.status}`)
      connect()
      // Refresh to pick up "extracting" status
      router.refresh()
    } catch {
      disconnect()
    } finally {
      setStarting(false)
    }
  }, [extractUrl, connect, disconnect, router])

  const handleCancel = useCallback(() => {
    disconnect()
  }, [disconnect])

  // ── Render ───────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-6">
      {/* Title row */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{book.title}</h1>
          <p className="text-sm text-muted-foreground">Extraction pipeline</p>
        </div>
        <ExtractionAction
          bookStatus={effectiveStatus}
          hasProfile={hasProfile}
          isFirstBook={isFirstBook}
          onStart={handleStart}
          onCancel={handleCancel}
          disabled={starting}
        />
      </div>

      {/* Error banner */}
      {isError && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Extraction stopped</AlertTitle>
          <AlertDescription>
            {chaptersDone} / {chaptersTotal} chapters extracted.{" "}
            {errorDetail?.message || `Status: ${book.status}`}
          </AlertDescription>
        </Alert>
      )}

      {/* Progress bar — visible when extracting or partially done */}
      {(isExtracting || (chaptersDone > 0 && !isDone)) && chaptersTotal > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              {isExtracting ? "Extracting..." : "Stopped"}
            </span>
            <span className="tabular-nums font-medium">
              {chaptersDone} / {chaptersTotal} chapters
              {totalEntities > 0 && (
                <span className="ml-2 text-muted-foreground">
                  · {totalEntities} entities
                </span>
              )}
            </span>
          </div>
          <Progress
            value={(chaptersDone / chaptersTotal) * 100}
            className={isError ? "[&>div]:bg-destructive" : ""}
          />
        </div>
      )}

      {/* Stats + Donut */}
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <ExtractionHeader
          entities={totalEntities}
          relations={totalRelations}
          chaptersDone={chaptersDone}
          chaptersTotal={chaptersTotal}
          cost={book.total_cost_usd}
        />
        <ExtractionDonut data={donutData} />
      </div>

      {/* Live feed — visible while running or after error */}
      {(isExtracting || isError) && feedMessages.length > 0 && (
        <div>
          <h2 className="mb-2 text-sm font-medium text-muted-foreground">Live feed</h2>
          <LiveFeed messages={feedMessages} />
        </div>
      )}

      {/* Chapter table */}
      <div>
        <h2 className="mb-2 text-sm font-medium text-muted-foreground">Chapters</h2>
        <ChapterTable chapters={chapterRows} />
      </div>
    </div>
  )
}
