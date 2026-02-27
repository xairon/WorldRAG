"use client"

import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import type { Neo4jSchemaInfo } from "@/lib/api/pipeline"

interface SchemaViewerProps {
  schema: Neo4jSchemaInfo
}

const TYPE_COLORS: Record<string, string> = {
  property: "text-blue-400 bg-blue-500/10 border-blue-500/20",
  fulltext: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  vector: "text-purple-400 bg-purple-500/10 border-purple-500/20",
  relationship: "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
}

export function SchemaViewer({ schema }: SchemaViewerProps) {
  return (
    <ScrollArea className="h-[65vh]">
      <div className="space-y-6">
        {/* Constraints */}
        <div>
          <h3 className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-3">
            Uniqueness Constraints ({schema.constraints.length})
          </h3>
          <div className="rounded-lg border border-slate-800 overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-slate-900/80 text-slate-500 text-[10px] uppercase">
                  <th className="text-left px-3 py-2 font-medium">Name</th>
                  <th className="text-left px-3 py-2 font-medium">Label</th>
                  <th className="text-left px-3 py-2 font-medium">Properties</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {schema.constraints.map((c) => (
                  <tr key={c.name} className="hover:bg-slate-900/40">
                    <td className="px-3 py-2 font-mono text-slate-300">{c.name}</td>
                    <td className="px-3 py-2 text-indigo-400">{c.label}</td>
                    <td className="px-3 py-2 text-slate-400">
                      {c.properties.map((p) => (
                        <code key={p} className="mr-2 text-[10px] bg-slate-900/60 rounded px-1 py-0.5">
                          {p}
                        </code>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Indexes */}
        <div>
          <h3 className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-3">
            Indexes ({schema.indexes.length})
          </h3>
          <div className="rounded-lg border border-slate-800 overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-slate-900/80 text-slate-500 text-[10px] uppercase">
                  <th className="text-left px-3 py-2 font-medium">Name</th>
                  <th className="text-left px-3 py-2 font-medium">Type</th>
                  <th className="text-left px-3 py-2 font-medium">Label</th>
                  <th className="text-left px-3 py-2 font-medium">Properties</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {schema.indexes.map((idx) => (
                  <tr key={idx.name} className="hover:bg-slate-900/40">
                    <td className="px-3 py-2 font-mono text-slate-300">{idx.name}</td>
                    <td className="px-3 py-2">
                      <Badge
                        variant="outline"
                        className={TYPE_COLORS[idx.index_type] ?? "text-slate-400"}
                      >
                        {idx.index_type}
                      </Badge>
                    </td>
                    <td className="px-3 py-2 text-indigo-400">{idx.label}</td>
                    <td className="px-3 py-2 text-slate-400">
                      {idx.properties.map((p) => (
                        <code key={p} className="mr-2 text-[10px] bg-slate-900/60 rounded px-1 py-0.5">
                          {p}
                        </code>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </ScrollArea>
  )
}
