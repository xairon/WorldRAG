"use client"

import { useCallback, useMemo } from "react"
import { Checkbox } from "@/components/ui/checkbox"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { FileText } from "lucide-react"
import { formatNumber, statusColor, cn } from "@/lib/utils"
import type { ChapterInfo } from "@/lib/api"

interface ChapterSelectorProps {
  chapters: ChapterInfo[]
  selected: Set<number>
  onSelectionChange: (selected: Set<number>) => void
  disabled?: boolean
}

export function ChapterSelector({
  chapters,
  selected,
  onSelectionChange,
  disabled,
}: ChapterSelectorProps) {
  const allSelected = chapters.length > 0 && selected.size === chapters.length
  const someSelected = selected.size > 0 && !allSelected

  const unextractedChapters = useMemo(
    () => chapters.filter((ch) => ch.entity_count === 0).map((ch) => ch.number),
    [chapters],
  )

  const selectAll = useCallback(() => {
    onSelectionChange(new Set(chapters.map((ch) => ch.number)))
  }, [chapters, onSelectionChange])

  const selectNone = useCallback(() => {
    onSelectionChange(new Set())
  }, [onSelectionChange])

  const selectUnextracted = useCallback(() => {
    onSelectionChange(new Set(unextractedChapters))
  }, [unextractedChapters, onSelectionChange])

  const toggleChapter = useCallback(
    (num: number) => {
      const next = new Set(selected)
      if (next.has(num)) next.delete(num)
      else next.add(num)
      onSelectionChange(next)
    },
    [selected, onSelectionChange],
  )

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-1.5">
          <Checkbox
            checked={allSelected ? true : someSelected ? "indeterminate" : false}
            onCheckedChange={(checked) => (checked ? selectAll() : selectNone())}
            disabled={disabled}
          />
          <span className="text-xs text-muted-foreground">
            {selected.size}/{chapters.length} selected
          </span>
        </div>
        <div className="flex gap-1.5 ml-auto">
          <Button
            variant="ghost"
            size="sm"
            onClick={selectAll}
            disabled={disabled}
            className="text-xs h-7"
          >
            Select All
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={selectNone}
            disabled={disabled || selected.size === 0}
            className="text-xs h-7"
          >
            Clear
          </Button>
          {unextractedChapters.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={selectUnextracted}
              disabled={disabled}
              className="text-xs h-7"
            >
              Unextracted ({unextractedChapters.length})
            </Button>
          )}
        </div>
      </div>

      <ScrollArea className="h-[60vh] rounded-lg border border-[var(--glass-border)]">
        <div className="divide-y divide-[var(--glass-border)]">
          {chapters.map((ch) => (
            <label
              key={ch.number}
              className={cn(
                "flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-colors",
                "hover:bg-accent",
                selected.has(ch.number) && "bg-accent",
                disabled && "opacity-50 cursor-not-allowed",
              )}
            >
              <Checkbox
                checked={selected.has(ch.number)}
                onCheckedChange={() => toggleChapter(ch.number)}
                disabled={disabled}
              />
              <span className="text-muted-foreground font-mono text-xs w-8 shrink-0">
                {ch.number}
              </span>
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <FileText className="h-3.5 w-3.5 text-muted-foreground/60 shrink-0" />
                <span className="text-sm truncate">
                  {ch.title || `Chapter ${ch.number}`}
                </span>
              </div>
              <span className="text-xs text-muted-foreground shrink-0">
                {formatNumber(ch.word_count)}w
              </span>
              {ch.entity_count > 0 && (
                <Badge variant="secondary" className="text-[10px] h-5 shrink-0">
                  {ch.entity_count} entities
                </Badge>
              )}
              {ch.regex_matches > 0 && (
                <Badge variant="outline" className="text-[10px] h-5 shrink-0">
                  {ch.regex_matches} regex
                </Badge>
              )}
              <span
                className={cn(
                  "text-[10px] font-medium px-1.5 py-0.5 rounded-full border shrink-0",
                  ch.entity_count > 0
                    ? statusColor("extracted")
                    : statusColor("pending"),
                )}
              >
                {ch.entity_count > 0 ? "done" : "pending"}
              </span>
            </label>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
