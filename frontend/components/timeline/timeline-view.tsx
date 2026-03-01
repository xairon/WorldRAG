"use client"

import { EventCard } from "./event-card"
import type { TimelineEvent } from "@/lib/api/types"

interface TimelineViewProps {
  events: TimelineEvent[]
  bookId: string
}

/** Group events by chapter for display. */
function groupByChapter(events: TimelineEvent[]): Map<number, TimelineEvent[]> {
  const map = new Map<number, TimelineEvent[]>()
  for (const ev of events) {
    const ch = ev.chapter ?? 0
    if (!map.has(ch)) map.set(ch, [])
    map.get(ch)!.push(ev)
  }
  return map
}

export function TimelineView({ events, bookId }: TimelineViewProps) {
  if (events.length === 0) {
    return (
      <div className="glass rounded-xl border-dashed p-12 text-center">
        <p className="text-muted-foreground">No events found with these filters.</p>
      </div>
    )
  }

  const chapters = groupByChapter(events)

  return (
    <div className="relative space-y-8">
      {/* Vertical line */}
      <div className="absolute left-[19px] top-0 bottom-0 w-px bg-[var(--glass-border)]" />

      {Array.from(chapters.entries()).map(([chapter, chapterEvents]) => (
        <div key={chapter} className="relative">
          {/* Chapter marker */}
          <div className="flex items-center gap-3 mb-3">
            <div className="relative z-10 flex h-10 w-10 items-center justify-center rounded-full bg-accent border border-[var(--glass-border)] text-xs font-bold text-primary">
              {chapter}
            </div>
            <span className="text-sm font-medium text-muted-foreground">
              Chapter {chapter}
            </span>
            <span className="text-xs text-muted-foreground/60">
              {chapterEvents.length} event{chapterEvents.length > 1 ? "s" : ""}
            </span>
          </div>

          {/* Events for this chapter */}
          <div className="ml-[52px] space-y-2">
            {chapterEvents.map((ev, i) => (
              <EventCard key={`${ev.name}-${i}`} event={ev} bookId={bookId} />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
