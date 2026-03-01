"use client"

import { ChevronLeft, ChevronRight } from "lucide-react"
import { useState } from "react"
import { Slider } from "@/components/ui/slider"
import { cn, LABEL_COLORS } from "@/lib/utils"
import { useGraphStore } from "@/stores/graph-store"

interface GraphControlsProps {
  totalChapters: number
}

export function GraphControls({
  totalChapters,
}: GraphControlsProps) {
  const { filters, toggleLabel, setFilters } = useGraphStore()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="glass rounded-2xl overflow-hidden">
      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed((prev) => !prev)}
        className="flex w-full items-center justify-between px-4 py-3 text-muted-foreground hover:text-foreground transition-colors"
      >
        <span className="font-display text-xs font-semibold uppercase tracking-widest">
          Filters
        </span>
        {collapsed ? (
          <ChevronRight className="h-4 w-4" />
        ) : (
          <ChevronLeft className="h-4 w-4" />
        )}
      </button>

      {!collapsed && (
        <div className="space-y-4 px-4 pb-4">
          {/* Entity type toggles */}
          <div>
            <h3 className="font-display text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-2">
              Entity Types
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(LABEL_COLORS).map(([label, color]) => {
                const active = filters.labels.length === 0 || filters.labels.includes(label)
                return (
                  <button
                    key={label}
                    onClick={() => toggleLabel(label)}
                    className={cn(
                      "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] border transition-all",
                      active
                        ? "glass text-foreground"
                        : "border-transparent bg-transparent text-muted-foreground opacity-50",
                    )}
                  >
                    <span
                      className="h-2 w-2 rounded-full shrink-0"
                      style={{ backgroundColor: active ? color : "var(--muted-foreground)" }}
                    />
                    {label}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Chapter range slider */}
          {totalChapters > 0 && (
            <div>
              <h3 className="font-display text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-2">
                Chapter Range
              </h3>
              <div className="px-1">
                <Slider
                  min={1}
                  max={totalChapters}
                  step={1}
                  value={
                    filters.chapterRange
                      ? [filters.chapterRange[0], filters.chapterRange[1]]
                      : [1, totalChapters]
                  }
                  onValueChange={(value) => {
                    if (value[0] === 1 && value[1] === totalChapters) {
                      setFilters({ chapterRange: null })
                    } else {
                      setFilters({ chapterRange: [value[0], value[1]] })
                    }
                  }}
                />
                <div className="flex justify-between mt-1 text-[10px] text-muted-foreground">
                  <span>Ch. {filters.chapterRange?.[0] ?? 1}</span>
                  <span>Ch. {filters.chapterRange?.[1] ?? totalChapters}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
