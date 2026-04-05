"use client"

import { useState } from "react"
import { ArrowUpDown, Layers } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { ConfidenceBar } from "@/components/ui/confidence-bar"
import { cn } from "@/lib/utils"
import type { OntologyEntityType } from "@/lib/api/graph"

const LAYER_STYLES: Record<string, string> = {
  core: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  genre: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  induced: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
}

const CATEGORY_STYLES: Record<string, string> = {
  Characters: "border-blue-300 dark:border-blue-700",
  Psychology: "border-yellow-300 dark:border-yellow-700",
  Social: "border-emerald-300 dark:border-emerald-700",
  Events: "border-rose-300 dark:border-rose-700",
  Narrative: "border-slate-300 dark:border-slate-700",
  World: "border-green-300 dark:border-green-700",
  Objects: "border-orange-300 dark:border-orange-700",
  Stoff: "border-violet-300 dark:border-violet-700",
  Textual: "border-cyan-300 dark:border-cyan-700",
  Bibliographic: "border-gray-300 dark:border-gray-700",
  Other: "border-gray-200 dark:border-gray-800",
}

type SortKey = "label" | "count" | "layer" | "avg_confidence"

function SortHeader({ label, field, onSort }: { label: string; field: SortKey; onSort: (field: SortKey) => void }) {
  return (
    <button onClick={() => onSort(field)} className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-slate-500 hover:text-slate-700 dark:hover:text-slate-300">
      {label}
      <ArrowUpDown className="h-3 w-3" />
    </button>
  )
}

export function EntityTypeTable({
  entityTypes,
  selectedType,
  groupByCategory = false,
}: {
  entityTypes: OntologyEntityType[]
  selectedType?: string | null
  groupByCategory?: boolean
}) {
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

  // Group by GOLEM category if enabled
  const groups: Map<string, typeof sorted> = new Map()
  if (groupByCategory) {
    for (const e of sorted) {
      const cat = (e as OntologyEntityType & { golem_category?: string }).golem_category || e.layer
      const list = groups.get(cat) ?? []
      list.push(e)
      groups.set(cat, list)
    }
  } else {
    groups.set("all", sorted)
  }

  function renderRow(e: OntologyEntityType) {
    const ext = e as OntologyEntityType & { golem_alignment?: string; description?: string }
    return (
      <tr
        key={e.label}
        className={cn(
          "transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/40",
          selectedType === e.label && "bg-accent",
        )}
      >
        <td className="px-5 py-2.5">
          <div>
            <span className="font-medium text-slate-800 dark:text-slate-200">{e.label}</span>
            {ext.golem_alignment && (
              <span className="ml-2 text-[10px] font-mono text-slate-400 dark:text-slate-500">
                {ext.golem_alignment}
              </span>
            )}
          </div>
          {ext.description && (
            <p className="mt-0.5 text-[11px] leading-tight text-slate-400 dark:text-slate-500 line-clamp-1">
              {ext.description}
            </p>
          )}
        </td>
        <td className="px-3 py-2.5">
          <Badge variant="secondary" className={LAYER_STYLES[e.layer] || ""}>
            {e.layer}
          </Badge>
        </td>
        <td className="px-3 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{e.count.toLocaleString()}</td>
        <td className="px-3 py-2.5">
          <div className="flex items-center gap-2">
            <div className="w-16">
              <ConfidenceBar value={e.avg_confidence} size="sm" />
            </div>
            <span className="text-xs text-slate-500">{Math.round(e.avg_confidence * 100)}%</span>
          </div>
        </td>
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
    )
  }

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/50">
      <div className="border-b border-slate-200 px-5 py-3 dark:border-slate-800">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
          Entity Types
          {groupByCategory && (
            <span className="ml-2 text-xs font-normal text-slate-400">grouped by GOLEM category</span>
          )}
        </h3>
      </div>
      <div className="max-h-[500px] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-slate-50 dark:bg-slate-800/80">
            <tr>
              <th className="px-5 py-2.5 text-left"><SortHeader label="Type" field="label" onSort={toggleSort} /></th>
              <th className="px-3 py-2.5 text-left"><SortHeader label="Layer" field="layer" onSort={toggleSort} /></th>
              <th className="px-3 py-2.5 text-right"><SortHeader label="Count" field="count" onSort={toggleSort} /></th>
              <th className="px-3 py-2.5 text-left"><SortHeader label="Confidence" field="avg_confidence" onSort={toggleSort} /></th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Samples</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {Array.from(groups.entries()).map(([category, types]) => (
              groupByCategory ? (
                <>{/* Category header row */}
                  <tr key={`cat-${category}`} className={cn("border-l-2", CATEGORY_STYLES[category] || "")}>
                    <td colSpan={5} className="px-5 py-2 bg-slate-50/50 dark:bg-slate-800/30">
                      <div className="flex items-center gap-2">
                        <Layers className="h-3.5 w-3.5 text-slate-400" />
                        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                          {category}
                        </span>
                        <span className="text-[10px] text-slate-400">({types.length} types)</span>
                      </div>
                    </td>
                  </tr>
                  {types.map(renderRow)}
                </>
              ) : (
                types.map(renderRow)
              )
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
