"use client"

import { Shield, ShieldOff } from "lucide-react"
import { Slider } from "@/components/ui/slider"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface SpoilerGuardProps {
  maxChapter: number | null
  totalChapters: number
  onChange: (chapter: number | null) => void
}

export function SpoilerGuard({ maxChapter, totalChapters, onChange }: SpoilerGuardProps) {
  const isActive = maxChapter !== null

  if (totalChapters <= 1) return null

  return (
    <div className={cn(
      "flex items-center gap-3 rounded-lg border px-3 py-2 text-xs transition-colors",
      isActive
        ? "border-amber-500/30 bg-amber-500/5"
        : "border-slate-700/50 bg-slate-800/30",
    )}>
      <Button
        variant="ghost"
        size="sm"
        className={cn("h-6 w-6 p-0", isActive && "text-amber-400")}
        onClick={() => onChange(isActive ? null : Math.min(5, totalChapters))}
      >
        {isActive ? (
          <Shield className="h-3.5 w-3.5" />
        ) : (
          <ShieldOff className="h-3.5 w-3.5 text-slate-500" />
        )}
      </Button>

      {isActive ? (
        <>
          <Slider
            min={1}
            max={totalChapters}
            value={[maxChapter]}
            onValueChange={([v]) => onChange(v)}
            className="flex-1 min-w-[120px]"
          />
          <span className="tabular-nums text-amber-400 font-medium whitespace-nowrap">
            Ch. 1–{maxChapter}
          </span>
        </>
      ) : (
        <span className="text-slate-500">Spoiler guard off</span>
      )}
    </div>
  )
}
