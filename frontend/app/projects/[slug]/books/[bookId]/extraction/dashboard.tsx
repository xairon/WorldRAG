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
  const {
    connect,
    disconnect,
    status,
    feedMessages,
    chaptersDone,
    chaptersTotal,
    entitiesFound,
    errorDetail,
  } = useExtractionStream(bookId)

  // Poll server data while extraction is running (SSE events can be missed)
  useEffect(() => {
    if (status === "done") {
      router.refresh()
      return
    }
    // Poll every 10s while extracting (book.status or SSE status indicates running)
    const shouldPoll = status === "running" || book.status === "extracting"
    if (!shouldPoll) return

    const interval = setInterval(() => {
      router.refresh() // Re-fetches server component data
    }, 10_000)

    return () => clearInterval(interval)
  }, [status, book.status, router])

  const extractUrl = `/api/books/${bookId}/extract/v4`

  // Auto-connect SSE if extraction is already running (page reload during extraction)
  useEffect(() => {
    if (book.status === "extracting" && status === "idle") {
      useExtractionStore.getState().setProgress({ chaptersTotal: book.total_chapters })
      useExtractionStore.getState().setStatus("running")
      connect()
    }
  }, [book.status, status, book.total_chapters, connect])

  const isRunning = status === "running"
  const isError = status === "error" || status === "error_quota"

  const effectiveStatus = isRunning
    ? "extracting"
    : isError
      ? "error"
      : book.status

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

  const totalEntities = useMemo(
    () => chapters.reduce((sum, ch) => sum + (ch.entity_count ?? 0), 0),
    [chapters],
  )

  const totalRelations = 0 // TODO: wire from API when available

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
      // Set total from known chapter count (avoids race with SSE "started" event)
      useExtractionStore.getState().setProgress({ chaptersTotal: book.total_chapters })
      // Now connect SSE for live progress updates
      connect()
    } catch {
      disconnect()
    } finally {
      setStarting(false)
    }
  }, [extractUrl, connect, disconnect, book.total_chapters])

  const handleCancel = useCallback(() => {
    disconnect()
  }, [disconnect])

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
      {isError && errorDetail && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Extraction stopped</AlertTitle>
          <AlertDescription>
            {chaptersDone} / {chaptersTotal} chapters extracted.{" "}
            {errorDetail.message || "An error occurred."}
          </AlertDescription>
        </Alert>
      )}

      {/* Progress bar */}
      {(isRunning || isError) && chaptersTotal > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              {isRunning ? "Extracting..." : "Stopped"}
            </span>
            <span className="tabular-nums font-medium">
              {chaptersDone} / {chaptersTotal} chapters
              {entitiesFound > 0 && (
                <span className="ml-2 text-muted-foreground">
                  · {entitiesFound} entities
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
          entities={isRunning ? entitiesFound : totalEntities}
          relations={totalRelations}
          chaptersDone={isRunning ? chaptersDone : chapters.filter((c) => mapBackendStatus(c.status) === "done").length}
          chaptersTotal={isRunning ? chaptersTotal : book.total_chapters}
          cost={book.total_cost_usd}
        />
        <ExtractionDonut data={donutData} />
      </div>

      {/* Live feed — visible while running or after error */}
      {(isRunning || isError) && feedMessages.length > 0 && (
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
