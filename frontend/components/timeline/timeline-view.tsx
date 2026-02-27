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
      <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/30 p-12 text-center">
        <p className="text-slate-500">No events found with these filters.</p>
      </div>
    )
  }

  const chapters = groupByChapter(events)

  return (
    <div className="relative space-y-8">
      {/* Vertical line */}
      <div className="absolute left-[19px] top-0 bottom-0 w-px bg-slate-800" />

      {Array.from(chapters.entries()).map(([chapter, chapterEvents]) => (
        <div key={chapter} className="relative">
          {/* Chapter marker */}
          <div className="flex items-center gap-3 mb-3">
            <div className="relative z-10 flex h-10 w-10 items-center justify-center rounded-full bg-slate-800 border border-slate-700 text-xs font-bold text-indigo-400">
              {chapter}
            </div>
            <span className="text-sm font-medium text-slate-400">
              Chapter {chapter}
            </span>
            <span className="text-xs text-slate-600">
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
