"use client"

import { useCallback, useMemo, useState } from "react"
import { ExtractionAction } from "@/components/extraction/extraction-action"
import { ExtractionHeader } from "@/components/extraction/extraction-header"
import { ExtractionDonut } from "@/components/extraction/extraction-donut"
import { ChapterTable, type ChapterData } from "@/components/extraction/chapter-table"
import { LiveFeed } from "@/components/extraction/live-feed"
import { useExtractionStream } from "@/hooks/use-extraction-stream"
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
  const [starting, setStarting] = useState(false)
  const { connect, disconnect, status, feedMessages, chaptersDone, chaptersTotal, entitiesFound } =
    useExtractionStream(bookId)

  const isRunning = status === "running"

  const effectiveStatus = isRunning ? "extracting" : book.status

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
    try {
      await fetch(`/api/projects/${slug}/extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ book_id: bookId }),
      })
      connect()
    } catch {
      // extraction-action will show error state via store
    } finally {
      setStarting(false)
    }
  }, [slug, bookId, connect])

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

      {/* Live feed — only visible while running */}
      {isRunning && (
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
