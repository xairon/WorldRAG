"use client"

import { motion, AnimatePresence } from "motion/react"
import { Progress } from "@/components/ui/progress"
import { SSEIndicator } from "@/components/ui/sse-indicator"
import type { SSEStatus } from "@/hooks/use-extraction"

interface ExtractionLiveStatsProps {
  totalEntities: number
  chaptersDone: number
  chaptersTotal: number
  sseStatus: SSEStatus
  costUsd?: number
}

export function ExtractionLiveStats({
  totalEntities,
  chaptersDone,
  chaptersTotal,
  sseStatus,
  costUsd,
}: ExtractionLiveStatsProps) {
  const pct = chaptersTotal > 0 ? (chaptersDone / chaptersTotal) * 100 : 0

  return (
    <div className="space-y-6">
      {/* Total entities */}
      <div className="text-center">
        <AnimatePresence mode="popLayout">
          <motion.p
            key={totalEntities}
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-4xl font-bold tabular-nums"
          >
            {totalEntities}
          </motion.p>
        </AnimatePresence>
        <p className="text-xs text-muted-foreground mt-1">entities extracted</p>
      </div>

      {/* Progress bar */}
      <div>
        <div className="flex justify-between text-xs text-muted-foreground mb-1.5">
          <span>Progress</span>
          <span className="tabular-nums">{chaptersDone}/{chaptersTotal}</span>
        </div>
        <Progress value={pct} className="h-2" />
      </div>

      {/* Cost */}
      {costUsd != null && costUsd > 0 && (
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">Cost</span>
          <span className="font-mono tabular-nums">${costUsd.toFixed(3)}</span>
        </div>
      )}

      {/* SSE status */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">Connection</span>
        <SSEIndicator status={sseStatus} />
      </div>
    </div>
  )
}
