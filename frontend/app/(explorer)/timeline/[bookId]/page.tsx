"use client"

import { useState, useEffect, useCallback } from "react"
import { useParams } from "next/navigation"
import { Clock, Filter } from "lucide-react"
import { getTimeline, getBook } from "@/lib/api"
import type { TimelineEvent, BookDetail } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { ScrollArea } from "@/components/ui/scroll-area"
import { TimelineView } from "@/components/timeline/timeline-view"

const SIGNIFICANCE_LEVELS = ["critical", "major", "moderate", "minor"] as const

export default function TimelinePage() {
  const params = useParams()
  const bookId = params.bookId as string

  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [bookDetail, setBookDetail] = useState<BookDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [significance, setSignificance] = useState<string>("moderate")
  const [character, setCharacter] = useState("")
  const [activeCharacter, setActiveCharacter] = useState<string | undefined>()

  const fetchTimeline = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getTimeline(bookId, significance || undefined, activeCharacter)
      setEvents(data)
    } catch {
      setEvents([])
    } finally {
      setLoading(false)
    }
  }, [bookId, significance, activeCharacter])

  useEffect(() => {
    getBook(bookId).then(setBookDetail).catch(() => {})
  }, [bookId])

  useEffect(() => {
    fetchTimeline()
  }, [fetchTimeline])

  function handleCharacterFilter(e: React.FormEvent) {
    e.preventDefault()
    setActiveCharacter(character.trim() || undefined)
  }

  function clearCharacterFilter() {
    setCharacter("")
    setActiveCharacter(undefined)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <Clock className="h-6 w-6 text-indigo-400" />
          <h1 className="text-2xl font-bold tracking-tight">Timeline</h1>
        </div>
        {bookDetail && (
          <p className="text-slate-400 text-sm mt-1">{bookDetail.book.title}</p>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Significance */}
        <div className="flex items-center gap-1.5">
          <Filter className="h-3.5 w-3.5 text-slate-500" />
          <span className="text-xs text-slate-500">Min:</span>
          {SIGNIFICANCE_LEVELS.map((level) => (
            <Button
              key={level}
              variant={significance === level ? "secondary" : "outline"}
              size="sm"
              className="h-7 text-xs capitalize"
              onClick={() => setSignificance(level)}
            >
              {level}
            </Button>
          ))}
        </div>

        {/* Character filter */}
        <form onSubmit={handleCharacterFilter} className="flex items-center gap-2">
          <Input
            value={character}
            onChange={(e) => setCharacter(e.target.value)}
            placeholder="Filter by character..."
            className="h-7 w-44 text-xs"
          />
          <Button type="submit" size="sm" variant="outline" className="h-7 text-xs">
            Apply
          </Button>
          {activeCharacter && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-7 text-xs text-slate-500"
              onClick={clearCharacterFilter}
            >
              Clear
            </Button>
          )}
        </form>

        <span className="text-xs text-slate-600 ml-auto">
          {loading ? "..." : `${events.length} events`}
        </span>
      </div>

      {/* Timeline */}
      {loading ? (
        <div className="space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : (
        <ScrollArea className="h-[calc(100vh-14rem)]">
          <TimelineView events={events} bookId={bookId} />
        </ScrollArea>
      )}
    </div>
  )
}
