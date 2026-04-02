"use client"

import { useState } from "react"
import { ChevronDown, ChevronRight } from "lucide-react"
import { getEntityHex } from "@/lib/constants"
import { cn } from "@/lib/utils"

interface GraphLegendProps {
  visibleTypes: Array<{ type: string; count: number }>
  activeLabels: string[]
  onToggle: (type: string) => void
}

export function GraphLegend({
  visibleTypes,
  activeLabels,
  onToggle,
}: GraphLegendProps) {
  const [collapsed, setCollapsed] = useState(false)

  if (visibleTypes.length === 0) return null

  return (
    <div className="absolute bottom-4 left-4 bg-background/90 backdrop-blur border rounded-lg shadow-lg z-10 text-xs">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center gap-1.5 px-3 py-2 w-full text-left font-medium"
      >
        {collapsed ? (
          <ChevronRight className="h-3 w-3" />
        ) : (
          <ChevronDown className="h-3 w-3" />
        )}
        Legend
        <span className="text-muted-foreground ml-1">
          ({visibleTypes.length})
        </span>
      </button>

      {!collapsed && (
        <div className="px-3 pb-2 space-y-0.5 max-h-48 overflow-auto">
          {visibleTypes.map(({ type, count }) => {
            const active =
              activeLabels.length === 0 || activeLabels.includes(type)
            return (
              <button
                key={type}
                onClick={() => onToggle(type)}
                className={cn(
                  "flex items-center gap-2 w-full px-1.5 py-1 rounded hover:bg-accent transition-opacity",
                  !active && "opacity-40",
                )}
              >
                <span
                  className="h-2.5 w-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: getEntityHex(type) }}
                />
                <span className="flex-1 text-left">{type}</span>
                <span className="text-muted-foreground tabular-nums">
                  {count}
                </span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
