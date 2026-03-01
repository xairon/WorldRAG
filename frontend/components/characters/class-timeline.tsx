"use client"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { ClassSnapshot } from "@/lib/api/characters"

interface ClassTimelineProps {
  classes: ClassSnapshot[]
}

export function ClassTimeline({ classes }: ClassTimelineProps) {
  if (classes.length === 0) {
    return (
      <div className="rounded-xl glass border-dashed p-8 text-center">
        <p className="text-sm text-muted-foreground">No classes acquired yet.</p>
      </div>
    )
  }

  // Sort by acquired chapter (ascending), active class first in case of ties
  const sorted = [...classes].sort((a, b) => {
    const chA = a.acquired_chapter ?? 0
    const chB = b.acquired_chapter ?? 0
    if (chA !== chB) return chA - chB
    // Active class comes first in ties
    if (a.is_active && !b.is_active) return -1
    if (!a.is_active && b.is_active) return 1
    return 0
  })

  return (
    <div className="relative space-y-0">
      {/* Vertical timeline line */}
      <div className="absolute left-[11px] top-4 bottom-4 w-px bg-[var(--border)]" />

      {sorted.map((cls, i) => (
        <div key={cls.name} className="relative flex gap-4 pb-4 last:pb-0">
          {/* Timeline node */}
          <div className="relative z-10 flex-shrink-0 mt-1">
            <div
              className={cn(
                "h-6 w-6 rounded-full border-2 flex items-center justify-center",
                cls.is_active
                  ? "border-emerald-500 bg-emerald-500/20"
                  : "border-[var(--glass-border)] bg-[var(--glass-bg)]",
              )}
            >
              {cls.is_active && (
                <div className="h-2 w-2 rounded-full bg-emerald-400" />
              )}
            </div>
          </div>

          {/* Class card */}
          <div
            className={cn(
              "flex-1 rounded-xl glass px-4 py-3",
              cls.is_active ? "border-emerald-500/20" : "",
            )}
          >
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-medium text-foreground">
                {cls.name}
              </span>
              {cls.is_active && (
                <Badge
                  variant="outline"
                  className="text-[10px] border-emerald-500/25 bg-emerald-500/10 text-emerald-400"
                >
                  Active
                </Badge>
              )}
              {cls.tier !== null && (
                <Badge
                  variant="outline"
                  className="text-[10px] border-amber-500/25 bg-amber-500/10 text-amber-400 font-mono"
                >
                  Tier {cls.tier}
                </Badge>
              )}
              {cls.acquired_chapter !== null && (
                <span className="text-[10px] text-muted-foreground/60 font-mono ml-auto">
                  Ch. {cls.acquired_chapter}
                </span>
              )}
            </div>
            {cls.description && (
              <p className="text-xs text-muted-foreground mt-1.5 line-clamp-2">
                {cls.description}
              </p>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
