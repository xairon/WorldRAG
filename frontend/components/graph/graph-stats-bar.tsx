"use client"

import { Minus, Plus, Maximize2 } from "lucide-react"
import { Button } from "@/components/ui/button"

interface GraphStatsBarProps {
  nodeCount: number
  edgeCount: number
  onZoomIn: () => void
  onZoomOut: () => void
  onZoomFit: () => void
}

export function GraphStatsBar({
  nodeCount,
  edgeCount,
  onZoomIn,
  onZoomOut,
  onZoomFit,
}: GraphStatsBarProps) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border/50 bg-background/80 backdrop-blur-sm shadow-sm px-3 py-1.5">
      {/* Stats */}
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span>
          <span className="font-mono font-medium text-foreground">{nodeCount.toLocaleString()}</span>{" "}
          nodes
        </span>
        <span className="text-border">|</span>
        <span>
          <span className="font-mono font-medium text-foreground">{edgeCount.toLocaleString()}</span>{" "}
          edges
        </span>
      </div>

      {/* Zoom controls */}
      <div className="flex items-center gap-0.5 ml-1">
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={onZoomOut}
          aria-label="Zoom out"
        >
          <Minus className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={onZoomFit}
          aria-label="Fit to screen"
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={onZoomIn}
          aria-label="Zoom in"
        >
          <Plus className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  )
}
