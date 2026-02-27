"use client"

import { useState } from "react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { PromptInfo } from "@/lib/api/pipeline"

interface PromptViewerProps {
  prompts: PromptInfo[]
}

export function PromptViewer({ prompts }: PromptViewerProps) {
  const [active, setActive] = useState(0)
  const current = prompts[active]

  if (prompts.length === 0) {
    return <p className="text-sm text-slate-500">No prompts loaded.</p>
  }

  return (
    <div className="flex gap-4 h-[65vh]">
      {/* Left: prompt list */}
      <div className="w-56 shrink-0 space-y-1">
        {prompts.map((p, i) => (
          <button
            key={p.name}
            onClick={() => setActive(i)}
            className={cn(
              "w-full text-left px-3 py-2 rounded-lg text-xs transition-colors",
              i === active
                ? "bg-indigo-500/15 text-indigo-300 border border-indigo-500/30"
                : "text-slate-400 hover:bg-slate-800/50 border border-transparent",
            )}
          >
            <div className="font-medium truncate">{p.pass_number}</div>
            <div className="text-[10px] text-slate-500 truncate">{p.name}</div>
          </button>
        ))}
      </div>

      {/* Right: prompt content */}
      <div className="flex-1 min-w-0 space-y-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium">{current.pass_number}</h3>
          {current.has_few_shot && (
            <Badge variant="secondary" className="text-[10px]">
              {current.few_shot_count} few-shot examples
            </Badge>
          )}
        </div>
        <ScrollArea className="h-[calc(65vh-3rem)] rounded-lg border border-slate-800 bg-slate-950/50">
          <pre className="p-4 text-xs text-slate-300 whitespace-pre-wrap font-mono leading-relaxed">
            {current.description}
          </pre>
        </ScrollArea>
      </div>
    </div>
  )
}
