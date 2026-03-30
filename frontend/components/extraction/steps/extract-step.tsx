"use client"

import { useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { useBookDetail } from "@/hooks/use-books"
import { useExtractionSSE, useRetryChapter } from "@/hooks/use-extraction"
import { ChapterProgressList } from "@/components/extraction/chapter-progress-list"
import { ExtractionLiveStats } from "@/components/extraction/extraction-live-stats"
import { ErrorState } from "@/components/ui/error-state"

interface ExtractStepProps {
  projectSlug: string
  bookId: string
  onComplete: () => void
}

export function ExtractStep({ projectSlug: _projectSlug, bookId, onComplete }: ExtractStepProps) {
  const { data: bookDetail } = useBookDetail(bookId)
  const sse = useExtractionSSE(bookId)
  const retryMutation = useRetryChapter()

  // Auto-connect on mount
  useEffect(() => {
    sse.connect()
    return () => sse.disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookId])

  // Auto-advance when done
  useEffect(() => {
    if (sse.isDone) {
      const timer = setTimeout(onComplete, 2000)
      return () => clearTimeout(timer)
    }
  }, [sse.isDone, onComplete])

  const chapters = bookDetail?.chapters ?? []

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Left: chapter list */}
      <div className="lg:col-span-2">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Chapters</CardTitle>
          </CardHeader>
          <CardContent className="max-h-[60vh] overflow-auto">
            <ChapterProgressList
              chapters={chapters}
              progress={sse.chapters}
              onRetry={(ch) => retryMutation.mutate({ bookId, chapter: ch })}
            />
          </CardContent>
        </Card>
      </div>

      {/* Right: live stats */}
      <div>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Progress</CardTitle>
          </CardHeader>
          <CardContent>
            <ExtractionLiveStats
              totalEntities={sse.totalEntities}
              chaptersDone={sse.chaptersDone}
              chaptersTotal={sse.chaptersTotal}
              sseStatus={sse.sseStatus}
            />
          </CardContent>
        </Card>

        {sse.error && (
          <ErrorState
            title="Extraction error"
            message={sse.error}
            onRetry={() => sse.connect()}
          />
        )}

        {sse.isDone && (
          <Card className="mt-4 border-emerald-500/50">
            <CardContent className="p-4 text-center">
              <p className="text-sm font-medium text-emerald-500">Extraction complete</p>
              <Button className="mt-3" size="sm" onClick={onComplete}>
                Review results
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
