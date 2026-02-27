"use client"

import Link from "next/link"
import { cn } from "@/lib/utils"
import { EntityBadge } from "@/components/shared/entity-badge"
import type { TimelineEvent } from "@/lib/api/types"

const SIGNIFICANCE_STYLES: Record<string, { dot: string; border: string }> = {
  critical: { dot: "bg-red-500", border: "border-red-500/30" },
  arc_defining: { dot: "bg-red-500", border: "border-red-500/30" },
  major: { dot: "bg-amber-500", border: "border-amber-500/30" },
  moderate: { dot: "bg-blue-500", border: "border-blue-500/30" },
  minor: { dot: "bg-slate-500", border: "border-slate-500/30" },
}

interface EventCardProps {
  event: TimelineEvent
  bookId: string
}

export function EventCard({ event, bookId }: EventCardProps) {
  const style = SIGNIFICANCE_STYLES[event.significance] ?? SIGNIFICANCE_STYLES.minor

  return (
    <div className={cn("rounded-lg border bg-slate-900/50 p-4", style.border)}>
      <div className="flex items-start gap-3">
        <div className={cn("mt-1.5 h-2.5 w-2.5 rounded-full shrink-0", style.dot)} />
        <div className="min-w-0 flex-1 space-y-2">
          {/* Header */}
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-medium text-slate-200 truncate">{event.name}</h3>
            <div className="flex items-center gap-2 shrink-0">
              {event.type && (
                <span className="text-[10px] uppercase tracking-wider text-slate-500">
                  {event.type.replace(/_/g, " ")}
                </span>
              )}
              <span className="text-[10px] uppercase tracking-wider text-slate-600">
                {event.significance}
              </span>
            </div>
          </div>

          {/* Description */}
          {event.description && (
            <p className="text-xs text-slate-400 leading-relaxed line-clamp-2">
              {event.description}
            </p>
          )}

          {/* Participants & Locations */}
          <div className="flex flex-wrap gap-1.5">
            {event.participants?.filter(Boolean).map((name) => (
              <EntityBadge key={name} name={name} type="Character" size="sm" />
            ))}
            {event.locations?.filter(Boolean).map((name) => (
              <EntityBadge key={name} name={name} type="Location" size="sm" />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
