"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { Slider } from "@/components/ui/slider"
import { cn } from "@/lib/utils"

interface ChapterSliderProps {
  chapter: number
  totalChapters: number
  onChange: (chapter: number) => void
}

export function ChapterSlider({ chapter, totalChapters, onChange }: ChapterSliderProps) {
  const [localValue, setLocalValue] = useState(chapter)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Sync local value when prop changes (e.g. URL navigation)
  useEffect(() => {
    setLocalValue(chapter)
  }, [chapter])

  const handleValueChange = useCallback(
    (values: number[]) => {
      const next = values[0]
      setLocalValue(next)

      if (timerRef.current) {
        clearTimeout(timerRef.current)
      }
      timerRef.current = setTimeout(() => {
        onChange(next)
      }, 300)
    },
    [onChange],
  )

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  return (
    <div className="rounded-xl glass px-5 py-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Chapter Progress
        </span>
        <span className="text-sm font-medium text-foreground">
          <span className="font-mono text-primary">{localValue}</span>
          <span className="text-muted-foreground mx-1">/</span>
          <span className="font-mono text-muted-foreground">{totalChapters}</span>
        </span>
      </div>
      <Slider
        min={1}
        max={totalChapters}
        step={1}
        value={[localValue]}
        onValueChange={handleValueChange}
        className={cn(
          "[&_[data-slot=slider-track]]:bg-[var(--border)]",
          "[&_[data-slot=slider-range]]:bg-[var(--primary)]",
          "[&_[data-slot=slider-thumb]]:border-[var(--primary)] [&_[data-slot=slider-thumb]]:bg-background",
        )}
      />
    </div>
  )
}
