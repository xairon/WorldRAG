"use client"

import { useState } from "react"
import { mapBackendStatus, getEntityHex } from "@/lib/constants"
import { formatNumber } from "@/lib/utils"
import { StatusBadge } from "@/components/shared/status-badge"
import type { ChapterData } from "./chapter-table"

interface ChapterRowProps {
  chapter: ChapterData
}

export function ChapterRow({ chapter }: ChapterRowProps) {
  const [expanded, setExpanded] = useState(false)
  const uiStatus = mapBackendStatus(chapter.status)
  const canExpand = uiStatus === "done" && chapter.entityCount > 0

  return (
    <>
      <tr
        className={
          canExpand
            ? "border-b cursor-pointer hover:bg-muted/50 transition-colors"
            : "border-b"
        }
        onClick={() => canExpand && setExpanded((prev) => !prev)}
      >
        <td className="px-3 py-2 font-mono text-muted-foreground tabular-nums">
          {chapter.number}
        </td>
        <td className="px-3 py-2">{chapter.title}</td>
        <td className="px-3 py-2 text-right font-mono tabular-nums">
          {formatNumber(chapter.words)}
        </td>
        <td className="px-3 py-2 text-right font-mono tabular-nums">
          {formatNumber(chapter.entityCount)}
        </td>
        <td className="px-3 py-2">
          <StatusBadge status={uiStatus} />
        </td>
      </tr>
      {expanded && canExpand && (
        <tr className="border-b bg-muted/30">
          <td />
          <td colSpan={4} className="px-3 py-2">
            <div className="flex flex-wrap gap-3">
              {chapter.entities
                .filter((e) => e.count > 0)
                .map((e) => (
                  <span
                    key={e.type}
                    className="inline-flex items-center gap-1.5 text-xs"
                  >
                    <span
                      className="inline-block size-2 rounded-full shrink-0"
                      style={{ backgroundColor: getEntityHex(e.type) }}
                    />
                    <span className="text-muted-foreground">{e.type}</span>
                    <span className="font-mono tabular-nums">
                      {formatNumber(e.count)}
                    </span>
                  </span>
                ))}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
