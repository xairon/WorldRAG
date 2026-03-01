"use client"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { StateChangeRecord } from "@/lib/api/characters"

interface ChangelogTabProps {
  changes: StateChangeRecord[]
}

const CATEGORY_STYLES: Record<string, string> = {
  stat: "border-blue-500/25 bg-blue-500/10 text-blue-400",
  skill: "border-emerald-500/25 bg-emerald-500/10 text-emerald-400",
  class: "border-amber-500/25 bg-amber-500/10 text-amber-400",
  title: "border-pink-500/25 bg-pink-500/10 text-pink-400",
  item: "border-violet-500/25 bg-violet-500/10 text-violet-400",
  level: "border-yellow-500/25 bg-yellow-500/10 text-yellow-400",
}

function categoryClass(category: string): string {
  return CATEGORY_STYLES[category.toLowerCase()] ?? "border-[var(--glass-border)] bg-accent text-muted-foreground"
}

export function ChangelogTab({ changes }: ChangelogTabProps) {
  if (changes.length === 0) {
    return (
      <div className="rounded-xl glass border-dashed p-8 text-center">
        <p className="text-sm text-muted-foreground">No changes in this chapter.</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {changes.map((change, i) => (
        <div
          key={`${change.category}-${change.name}-${i}`}
          className="rounded-xl glass px-4 py-3 flex items-start gap-3"
        >
          {/* Timeline dot */}
          <div className="flex flex-col items-center pt-1.5">
            <div className="h-2 w-2 rounded-full bg-muted-foreground" />
            {i < changes.length - 1 && (
              <div className="w-px flex-1 bg-[var(--border)] mt-1" />
            )}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0 space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge
                variant="outline"
                className={cn("text-[10px]", categoryClass(change.category))}
              >
                {change.category}
              </Badge>
              <span className="text-sm text-foreground">
                <span className="text-muted-foreground">{change.action}</span>{" "}
                <span className="font-medium">{change.name}</span>
              </span>
              {change.value_delta !== null && change.value_delta !== 0 && (
                <span
                  className={cn(
                    "text-xs font-mono font-semibold",
                    change.value_delta > 0 ? "text-emerald-400" : "text-red-400",
                  )}
                >
                  {change.value_delta > 0 ? "+" : ""}
                  {change.value_delta}
                  {change.value_after !== null && (
                    <span className="text-muted-foreground/60 ml-1">
                      ({change.value_after})
                    </span>
                  )}
                </span>
              )}
            </div>
            {change.detail && (
              <p className="text-xs text-muted-foreground line-clamp-2">{change.detail}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
