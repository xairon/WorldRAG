"use client"

import { STATUS_CONFIG, type UIStatus } from "@/lib/constants"
import { cn } from "@/lib/utils"

const STATUS_ICONS: Record<UIStatus, string> = {
  pending: "○",
  parsing: "○",
  ready: "◐",
  extracting: "◌",
  embedding: "◌",
  done: "●",
  error: "✕",
}

export function StatusBadge({ status, className }: { status: UIStatus; className?: string }) {
  const config = STATUS_CONFIG[status]
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-xs font-mono",
        status === "extracting" && "animate-pulse",
        status === "embedding" && "animate-pulse",
        className,
      )}
    >
      {/* Use inline style — dynamic Tailwind classes get purged */}
      <span style={{ color: config.hex }}>{STATUS_ICONS[status]}</span>
      <span className="text-muted-foreground">{config.label}</span>
    </span>
  )
}
