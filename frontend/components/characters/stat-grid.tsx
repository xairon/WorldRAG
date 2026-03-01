"use client"

import { cn } from "@/lib/utils"
import type { StatEntry, StateChangeRecord } from "@/lib/api/characters"

interface StatGridProps {
  stats: StatEntry[]
  chapterChanges: StateChangeRecord[]
}

export function StatGrid({ stats, chapterChanges }: StatGridProps) {
  // Build a map of stat name -> delta from this chapter's changes
  const deltaMap = new Map<string, number>()
  for (const change of chapterChanges) {
    if (change.category === "stat" && change.value_delta !== null) {
      const existing = deltaMap.get(change.name) ?? 0
      deltaMap.set(change.name, existing + change.value_delta)
    }
  }

  if (stats.length === 0) {
    return (
      <div className="rounded-xl glass border-dashed p-8 text-center">
        <p className="text-sm text-muted-foreground">No stats recorded yet.</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {stats.map((stat) => {
        const delta = deltaMap.get(stat.name)

        return (
          <div
            key={stat.name}
            className={cn(
              "rounded-xl glass px-4 py-3 flex items-center justify-between",
              delta !== undefined && delta !== 0
                ? delta > 0
                  ? "border-emerald-500/20"
                  : "border-red-500/20"
                : "",
            )}
          >
            <div className="flex flex-col gap-0.5">
              <span className="text-xs text-muted-foreground uppercase tracking-wider">
                {stat.name}
              </span>
              <span className="text-lg font-bold font-mono text-foreground">
                {stat.value}
              </span>
            </div>

            {delta !== undefined && delta !== 0 && (
              <span
                className={cn(
                  "text-sm font-mono font-semibold px-2 py-0.5 rounded-md",
                  delta > 0
                    ? "text-emerald-400 bg-emerald-500/10"
                    : "text-red-400 bg-red-500/10",
                )}
              >
                {delta > 0 ? "+" : ""}
                {delta}
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}
