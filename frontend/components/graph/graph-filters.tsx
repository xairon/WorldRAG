"use client"

import { useState } from "react"
import { ChevronDown, ChevronRight } from "lucide-react"
import { Checkbox } from "@/components/ui/checkbox"
import { Slider } from "@/components/ui/slider"
import { getEntityHex } from "@/lib/constants"

interface EntityTypeInfo {
  type: string
  count: number
}

interface GraphFiltersState {
  enabledTypes: Set<string>
  chapterRange: [number, number]
}

interface GraphFiltersProps {
  availableTypes: EntityTypeInfo[]
  maxChapter: number
  filters: GraphFiltersState
  onChange: (filters: GraphFiltersState) => void
}

export type { GraphFiltersState, EntityTypeInfo }

export function GraphFilters({ availableTypes, maxChapter, filters, onChange }: GraphFiltersProps) {
  const [collapsed, setCollapsed] = useState(false)

  function toggleType(type: string) {
    const next = new Set(filters.enabledTypes)
    if (next.has(type)) {
      next.delete(type)
    } else {
      next.add(type)
    }
    onChange({ ...filters, enabledTypes: next })
  }

  function handleChapterChange(value: number[]) {
    onChange({ ...filters, chapterRange: [value[0], value[1]] })
  }

  return (
    <div className="w-72 rounded-lg border border-border/50 bg-background/80 backdrop-blur-sm shadow-sm">
      <button
        onClick={() => setCollapsed((prev) => !prev)}
        className="flex w-full items-center justify-between px-3 py-2.5 text-muted-foreground hover:text-foreground transition-colors"
      >
        <span className="text-xs font-semibold uppercase tracking-wider">Filters</span>
        {collapsed ? (
          <ChevronRight className="h-4 w-4" />
        ) : (
          <ChevronDown className="h-4 w-4" />
        )}
      </button>

      {!collapsed && (
        <div className="space-y-4 px-3 pb-3">
          {/* Entity type checkboxes */}
          <div>
            <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
              Entity Types
            </h4>
            <div className="space-y-1.5">
              {availableTypes.map(({ type, count }) => {
                const checked = filters.enabledTypes.has(type)
                return (
                  <label
                    key={type}
                    className="flex items-center gap-2 cursor-pointer group"
                  >
                    <Checkbox
                      checked={checked}
                      onCheckedChange={() => toggleType(type)}
                      className="h-3.5 w-3.5"
                    />
                    <span
                      className="h-2 w-2 rounded-full shrink-0"
                      style={{ backgroundColor: getEntityHex(type) }}
                    />
                    <span className="text-xs text-foreground group-hover:text-foreground/80 flex-1">
                      {type}
                    </span>
                    <span className="text-[10px] text-muted-foreground font-mono">{count}</span>
                  </label>
                )
              })}
            </div>
          </div>

          {/* Chapter range dual slider */}
          {maxChapter > 1 && (
            <div>
              <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                Chapter Range
              </h4>
              <div className="px-1">
                <Slider
                  min={1}
                  max={maxChapter}
                  step={1}
                  value={[filters.chapterRange[0], filters.chapterRange[1]]}
                  onValueChange={handleChapterChange}
                />
                <div className="flex justify-between mt-1.5 text-[10px] text-muted-foreground font-mono">
                  <span>Ch. {filters.chapterRange[0]}</span>
                  <span>Ch. {filters.chapterRange[1]}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
