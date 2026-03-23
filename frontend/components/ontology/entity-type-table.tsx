"use client"

import { useState } from "react"
import { ArrowUpDown } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import type { OntologyEntityType } from "@/lib/api/graph"

const LAYER_STYLES: Record<string, string> = {
  core: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  genre: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  induced: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
}

type SortKey = "label" | "count" | "layer" | "avg_confidence"

export function EntityTypeTable({ entityTypes }: { entityTypes: OntologyEntityType[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("count")
  const [sortAsc, setSortAsc] = useState(false)

  const sorted = [...entityTypes].sort((a, b) => {
    const va = a[sortKey]
    const vb = b[sortKey]
    if (typeof va === "number" && typeof vb === "number") return sortAsc ? va - vb : vb - va
    return sortAsc ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va))
  })

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortAsc(!sortAsc)
    else {
      setSortKey(key)
      setSortAsc(false)
    }
  }

  function ConfidenceBar({ value }: { value: number }) {
    const pct = Math.round(value * 100)
    const color = value < 0.5 ? "bg-red-500" : value < 0.7 ? "bg-yellow-500" : "bg-emerald-500"
    return (
      <div className="flex items-center gap-2">
        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
          <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
        </div>
        <span className="text-xs text-slate-500">{pct}%</span>
      </div>
    )
  }

  function SortHeader({ label, field }: { label: string; field: SortKey }) {
    return (
      <button onClick={() => toggleSort(field)} className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-slate-500 hover:text-slate-700 dark:hover:text-slate-300">
        {label}
        <ArrowUpDown className="h-3 w-3" />
      </button>
    )
  }

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/50">
      <div className="border-b border-slate-200 px-5 py-3 dark:border-slate-800">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">Entity Types</h3>
      </div>
      <div className="max-h-[400px] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-slate-50 dark:bg-slate-800/80">
            <tr>
              <th className="px-5 py-2.5 text-left"><SortHeader label="Type" field="label" /></th>
              <th className="px-3 py-2.5 text-left"><SortHeader label="Layer" field="layer" /></th>
              <th className="px-3 py-2.5 text-right"><SortHeader label="Count" field="count" /></th>
              <th className="px-3 py-2.5 text-left"><SortHeader label="Confidence" field="avg_confidence" /></th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Samples</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {sorted.map((e) => (
              <tr key={e.label} className="transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/40">
                <td className="px-5 py-2.5 font-medium text-slate-800 dark:text-slate-200">{e.label}</td>
                <td className="px-3 py-2.5">
                  <Badge variant="secondary" className={LAYER_STYLES[e.layer] || ""}>
                    {e.layer}
                  </Badge>
                </td>
                <td className="px-3 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{e.count.toLocaleString()}</td>
                <td className="px-3 py-2.5"><ConfidenceBar value={e.avg_confidence} /></td>
                <td className="px-3 py-2.5">
                  <div className="flex flex-wrap gap-1">
                    {e.sample_entities.slice(0, 3).map((s) => (
                      <span key={s} className="inline-block rounded-md bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                        {s}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
