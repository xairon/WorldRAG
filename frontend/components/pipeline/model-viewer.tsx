"use client"

import { useMemo } from "react"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { ExtractionModelInfo } from "@/lib/api/pipeline"

interface ModelViewerProps {
  models: ExtractionModelInfo[]
}

export function ModelViewer({ models }: ModelViewerProps) {
  const grouped = useMemo(() => {
    const groups: Record<string, ExtractionModelInfo[]> = {}
    for (const m of models) {
      const key = m.pass_name
      if (!groups[key]) groups[key] = []
      groups[key].push(m)
    }
    return groups
  }, [models])

  if (models.length === 0) {
    return <p className="text-sm text-muted-foreground">No extraction models loaded.</p>
  }

  return (
    <ScrollArea className="h-[65vh]">
      <Accordion type="multiple" defaultValue={Object.keys(grouped)} className="space-y-2">
        {Object.entries(grouped).map(([passName, items]) => (
          <AccordionItem
            key={passName}
            value={passName}
            className="border border-[var(--glass-border)] rounded-lg px-4"
          >
            <AccordionTrigger className="text-sm font-medium hover:no-underline">
              <div className="flex items-center gap-2">
                <span>{passName}</span>
                <Badge variant="secondary" className="text-[10px]">
                  {items.length} models
                </Badge>
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-4 pb-2">
                {items.map((model) => (
                  <div key={model.name}>
                    <h4 className="text-xs font-mono text-primary mb-2">{model.name}</h4>
                    <div className="rounded-md border border-[var(--glass-border)]/60 overflow-hidden">
                      <table className="w-full text-[11px]">
                        <thead>
                          <tr className="bg-background text-muted-foreground text-[10px] uppercase">
                            <th className="text-left px-3 py-1.5 font-medium">Field</th>
                            <th className="text-left px-3 py-1.5 font-medium">Type</th>
                            <th className="text-center px-3 py-1.5 font-medium">Req</th>
                            <th className="text-left px-3 py-1.5 font-medium">Default</th>
                            <th className="text-left px-3 py-1.5 font-medium">Description</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[var(--glass-border)]">
                          {model.fields.map((f) => (
                            <tr key={f.name}>
                              <td className="px-3 py-1.5 font-mono text-foreground">{f.name}</td>
                              <td className="px-3 py-1.5 text-amber-300/80 font-mono">{f.type}</td>
                              <td className="px-3 py-1.5 text-center">
                                {f.required ? (
                                  <span className="text-red-400">*</span>
                                ) : (
                                  ""
                                )}
                              </td>
                              <td className="px-3 py-1.5 text-muted-foreground">
                                {f.default ?? ""}
                              </td>
                              <td className="px-3 py-1.5 text-muted-foreground max-w-[200px] truncate">
                                {f.description}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </ScrollArea>
  )
}
