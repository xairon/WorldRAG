"use client"

import { ZoomIn, ZoomOut, Maximize2, RotateCcw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn, LABEL_COLORS } from "@/lib/utils"
import { useGraphStore } from "@/stores/graph-store"

interface GraphControlsProps {
  totalChapters: number
  onZoomIn: () => void
  onZoomOut: () => void
  onResetZoom: () => void
}

export function GraphControls({
  totalChapters,
  onZoomIn,
  onZoomOut,
  onResetZoom,
}: GraphControlsProps) {
  const { filters, toggleLabel, setFilters } = useGraphStore()

  return (
    <div className="space-y-4">
      {/* Entity type toggles */}
      <div>
        <h3 className="text-[10px] font-semibold uppercase tracking-widest text-slate-600 mb-2">
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
                    ? "border-white/20 bg-white/5 text-slate-200"
                    : "border-slate-800 bg-slate-900/50 text-slate-600 opacity-50",
                )}
              >
                <span
                  className="h-2 w-2 rounded-full shrink-0"
                  style={{ backgroundColor: active ? color : "#334155" }}
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
          <h3 className="text-[10px] font-semibold uppercase tracking-widest text-slate-600 mb-2">
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
            <div className="flex justify-between mt-1 text-[10px] text-slate-600">
              <span>Ch. {filters.chapterRange?.[0] ?? 1}</span>
              <span>Ch. {filters.chapterRange?.[1] ?? totalChapters}</span>
            </div>
          </div>
        </div>
      )}

      {/* Zoom controls */}
      <div>
        <h3 className="text-[10px] font-semibold uppercase tracking-widest text-slate-600 mb-2">
          View
        </h3>
        <div className="flex gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="outline" size="icon" className="h-8 w-8" onClick={onZoomIn}>
                <ZoomIn className="h-3.5 w-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Zoom in</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="outline" size="icon" className="h-8 w-8" onClick={onZoomOut}>
                <ZoomOut className="h-3.5 w-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Zoom out</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="outline" size="icon" className="h-8 w-8" onClick={onResetZoom}>
                <Maximize2 className="h-3.5 w-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Fit to screen</TooltipContent>
          </Tooltip>
        </div>
      </div>

      {/* Stats */}
      <div>
        <h3 className="text-[10px] font-semibold uppercase tracking-widest text-slate-600 mb-1">
          Graph Stats
        </h3>
        <GraphStatsDisplay />
      </div>
    </div>
  )
}

function GraphStatsDisplay() {
  const { graphData } = useGraphStore()
  return (
    <div className="text-xs text-slate-500 space-y-0.5">
      <div>{graphData.nodes.length} nodes</div>
      <div>{graphData.edges.length} edges</div>
    </div>
  )
}
