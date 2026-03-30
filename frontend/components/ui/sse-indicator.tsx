"use client"

import { cn } from "@/lib/utils"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type { SSEStatus } from "@/hooks/use-extraction"

interface SSEIndicatorProps {
  status: SSEStatus
}

const STATUS_CONFIG: Record<SSEStatus, { label: string; dotClass: string }> = {
  connected: {
    label: "Connected",
    dotClass: "bg-green-500",
  },
  connecting: {
    label: "Connecting…",
    dotClass: "bg-amber-500 animate-pulse",
  },
  reconnecting: {
    label: "Reconnecting…",
    dotClass: "bg-amber-500 animate-pulse",
  },
  disconnected: {
    label: "Disconnected",
    dotClass: "bg-red-500",
  },
}

export function SSEIndicator({ status }: SSEIndicatorProps) {
  const config = STATUS_CONFIG[status]

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={cn("inline-block h-2 w-2 rounded-full", config.dotClass)}
            aria-label={config.label}
          />
        </TooltipTrigger>
        <TooltipContent>
          <p>{config.label}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
