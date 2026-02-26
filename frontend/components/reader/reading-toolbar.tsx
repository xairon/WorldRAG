"use client"

import { Eye, EyeOff } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn, LABEL_COLORS } from "@/lib/utils"

type ReadingMode = "annotated" | "clean" | "focus"

interface ReadingToolbarProps {
  mode: ReadingMode
  enabledTypes: Set<string>
  onModeChange: (mode: ReadingMode) => void
  onToggleType: (type: string) => void
  annotationCount: number
  typeCounts: Record<string, number>
}

export function ReadingToolbar({
  mode,
  enabledTypes,
  onModeChange,
  onToggleType,
  annotationCount,
  typeCounts,
}: ReadingToolbarProps) {
  const isClean = mode === "clean"

  return (
    <div className="flex items-center gap-3 flex-wrap">
      {/* Master toggle */}
      <Button
        variant={isClean ? "outline" : "secondary"}
        size="sm"
        className="h-7 text-xs"
        onClick={() => onModeChange(isClean ? "annotated" : "clean")}
      >
        {isClean ? (
          <><EyeOff className="h-3 w-3 mr-1" /> Off</>
        ) : (
          <><Eye className="h-3 w-3 mr-1" /> {annotationCount}</>
        )}
      </Button>

      {/* Entity type toggles */}
      {!isClean && (
        <div className="flex items-center gap-1 flex-wrap">
          {Object.entries(LABEL_COLORS).map(([label, color]) => {
            const count = typeCounts[label] ?? 0
            if (count === 0) return null
            const active = enabledTypes.has(label)
            return (
              <button
                key={label}
                onClick={() => onToggleType(label)}
                className={cn(
                  "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium transition-all",
                  active
                    ? "opacity-100"
                    : "opacity-40 hover:opacity-70"
                )}
                style={{
                  backgroundColor: active ? `${color}20` : "transparent",
                  border: `1px solid ${active ? color + "50" : "transparent"}`,
                  color: active ? color : undefined,
                }}
              >
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ backgroundColor: color }}
                />
                {label}
                <span className="text-[9px] opacity-70">{count}</span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
