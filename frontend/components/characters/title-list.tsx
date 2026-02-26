"use client"

import { Badge } from "@/components/ui/badge"
import type { TitleSnapshot } from "@/lib/api/characters"

interface TitleListProps {
  titles: TitleSnapshot[]
}

export function TitleList({ titles }: TitleListProps) {
  if (titles.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-8 text-center">
        <p className="text-sm text-slate-500">No titles acquired yet.</p>
      </div>
    )
  }

  const sorted = [...titles].sort(
    (a, b) => (a.acquired_chapter ?? 0) - (b.acquired_chapter ?? 0),
  )

  return (
    <div className="space-y-2">
      {sorted.map((title) => (
        <div
          key={title.name}
          className="rounded-xl bg-slate-900/50 border border-slate-800 px-4 py-3"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-col gap-1 min-w-0">
              <span className="text-sm font-medium text-slate-200">
                {title.name}
              </span>
              {title.description && (
                <p className="text-xs text-slate-500 line-clamp-2">
                  {title.description}
                </p>
              )}
              {title.effects.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {title.effects.map((effect, i) => (
                    <Badge
                      key={`${effect}-${i}`}
                      variant="outline"
                      className="text-[10px] border-pink-500/25 bg-pink-500/10 text-pink-400"
                    >
                      {effect}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
            {title.acquired_chapter !== null && (
              <span className="text-[10px] text-slate-600 font-mono whitespace-nowrap mt-0.5">
                Ch. {title.acquired_chapter}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
