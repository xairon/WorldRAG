"use client"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { ItemSnapshot } from "@/lib/api/characters"

interface EquipmentListProps {
  items: ItemSnapshot[]
}

const RARITY_COLORS: Record<string, string> = {
  common: "border-slate-600 bg-slate-500/10 text-slate-400",
  uncommon: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  rare: "border-blue-500/30 bg-blue-500/10 text-blue-400",
  epic: "border-violet-500/30 bg-violet-500/10 text-violet-400",
  legendary: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  unique: "border-rose-500/30 bg-rose-500/10 text-rose-400",
}

function rarityClass(rarity: string): string {
  return RARITY_COLORS[rarity.toLowerCase()] ?? RARITY_COLORS.common
}

export function EquipmentList({ items }: EquipmentListProps) {
  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-8 text-center">
        <p className="text-sm text-slate-500">No items acquired yet.</p>
      </div>
    )
  }

  const sorted = [...items].sort(
    (a, b) => (a.acquired_chapter ?? 0) - (b.acquired_chapter ?? 0),
  )

  return (
    <div className="space-y-2">
      {sorted.map((item) => (
        <div
          key={item.name}
          className="rounded-xl bg-slate-900/50 border border-slate-800 px-4 py-3"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex flex-col gap-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium text-slate-200">
                  {item.name}
                </span>
                {item.rarity && (
                  <Badge
                    variant="outline"
                    className={cn("text-[10px]", rarityClass(item.rarity))}
                  >
                    {item.rarity}
                  </Badge>
                )}
                {item.item_type && (
                  <Badge
                    variant="outline"
                    className="text-[10px] border-slate-700 text-slate-500"
                  >
                    {item.item_type}
                  </Badge>
                )}
              </div>
              {item.description && (
                <p className="text-xs text-slate-500 line-clamp-2">
                  {item.description}
                </p>
              )}
              {item.grants.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {item.grants.map((grant) => (
                    <Badge
                      key={grant}
                      variant="outline"
                      className="text-[10px] border-indigo-500/25 bg-indigo-500/10 text-indigo-400"
                    >
                      {grant}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
            {item.acquired_chapter !== null && (
              <span className="text-[10px] text-slate-600 font-mono whitespace-nowrap mt-0.5">
                Ch. {item.acquired_chapter}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
