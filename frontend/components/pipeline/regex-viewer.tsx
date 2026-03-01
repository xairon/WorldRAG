"use client"

import { useMemo } from "react"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { labelBadgeClass } from "@/lib/utils"
import type { RegexPatternInfo } from "@/lib/api/pipeline"

interface RegexViewerProps {
  patterns: RegexPatternInfo[]
}

export function RegexViewer({ patterns }: RegexViewerProps) {
  const grouped = useMemo(() => {
    const groups: Record<string, RegexPatternInfo[]> = {}
    for (const p of patterns) {
      const key = p.source
      if (!groups[key]) groups[key] = []
      groups[key].push(p)
    }
    return groups
  }, [patterns])

  if (patterns.length === 0) {
    return <p className="text-sm text-muted-foreground">No regex patterns loaded.</p>
  }

  return (
    <ScrollArea className="h-[65vh]">
      <div className="space-y-6">
        {Object.entries(grouped).map(([source, items]) => (
          <div key={source}>
            <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
              {source}
            </h3>
            <div className="rounded-lg border border-[var(--glass-border)] overflow-hidden">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-background text-muted-foreground text-[10px] uppercase">
                    <th className="text-left px-3 py-2 font-medium">Name</th>
                    <th className="text-left px-3 py-2 font-medium">Type</th>
                    <th className="text-left px-3 py-2 font-medium">Pattern</th>
                    <th className="text-left px-3 py-2 font-medium">Captures</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--glass-border)]">
                  {items.map((p) => (
                    <tr key={p.name} className="hover:bg-accent">
                      <td className="px-3 py-2 font-mono text-foreground">{p.name}</td>
                      <td className="px-3 py-2">
                        <Badge className={labelBadgeClass(p.entity_type)} variant="outline">
                          {p.entity_type}
                        </Badge>
                      </td>
                      <td className="px-3 py-2">
                        <code className="text-[10px] text-amber-300/80 bg-background rounded px-1.5 py-0.5 break-all">
                          {p.pattern}
                        </code>
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {Object.entries(p.captures).map(([k, v]) => (
                          <span key={k} className="mr-2">
                            {k}:<span className="text-muted-foreground">{v}</span>
                          </span>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </ScrollArea>
  )
}
