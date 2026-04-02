"use client"

import { useState, useMemo } from "react"
import { ArrowUpDown, Clock, Minus } from "lucide-react"
import type { OntologyRelationType, OntologySchemaEdge } from "@/lib/api/graph"

type SortKey = "type" | "count" | "temporal"

function SortHeader({ label, field, onSort }: { label: string; field: SortKey; onSort: (field: SortKey) => void }) {
  return (
    <button onClick={() => onSort(field)} className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-slate-500 hover:text-slate-700 dark:hover:text-slate-300">
      {label}
      <ArrowUpDown className="h-3 w-3" />
    </button>
  )
}

export function RelationTypeTable({
  relationTypes,
  schemaEdges,
  selectedType,
}: {
  relationTypes: OntologyRelationType[]
  schemaEdges: OntologySchemaEdge[]
  selectedType?: string | null
}) {
  const [sortKey, setSortKey] = useState<SortKey>("count")
  const [sortAsc, setSortAsc] = useState(false)

  // Build source->target mapping from schema edges
  const pairMap = useMemo(() => {
    const m = new Map<string, Set<string>>()
    for (const e of schemaEdges) {
      const key = e.relation
      if (!m.has(key)) m.set(key, new Set())
      m.get(key)!.add(`${e.source} -> ${e.target}`)
    }
    return m
  }, [schemaEdges])

  // Build set of relation types connected to the selected entity type
  const filteredRelationTypes = useMemo(() => {
    if (!selectedType) return relationTypes
    const relevantTypes = new Set<string>()
    for (const e of schemaEdges) {
      if (e.source === selectedType || e.target === selectedType) {
        relevantTypes.add(e.relation)
      }
    }
    return relationTypes.filter((r) => relevantTypes.has(r.type))
  }, [relationTypes, schemaEdges, selectedType])

  const sorted = [...filteredRelationTypes].sort((a, b) => {
    if (sortKey === "type") return sortAsc ? a.type.localeCompare(b.type) : b.type.localeCompare(a.type)
    if (sortKey === "temporal") return sortAsc ? (a.temporal ? 1 : -1) : b.temporal ? 1 : -1
    return sortAsc ? a.count - b.count : b.count - a.count
  })

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortAsc(!sortAsc)
    else {
      setSortKey(key)
      setSortAsc(false)
    }
  }

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/50">
      <div className="border-b border-slate-200 px-5 py-3 dark:border-slate-800">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">
          Relation Types
          {selectedType && (
            <span className="ml-2 text-xs font-normal text-slate-500">
              filtered by {selectedType}
            </span>
          )}
        </h3>
      </div>
      <div className="max-h-[400px] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-slate-50 dark:bg-slate-800/80">
            <tr>
              <th className="px-5 py-2.5 text-left"><SortHeader label="Type" field="type" onSort={toggleSort} /></th>
              <th className="px-3 py-2.5 text-right"><SortHeader label="Count" field="count" onSort={toggleSort} /></th>
              <th className="px-3 py-2.5 text-center"><SortHeader label="Temporal" field="temporal" onSort={toggleSort} /></th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">Endpoints</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {sorted.map((r) => {
              const pairs = pairMap.get(r.type)
              const pairList = pairs ? [...pairs].slice(0, 2) : []
              return (
                <tr key={r.type} className="transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/40">
                  <td className="px-5 py-2.5 font-mono text-xs font-medium text-slate-800 dark:text-slate-200">{r.type}</td>
                  <td className="px-3 py-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{r.count.toLocaleString()}</td>
                  <td className="px-3 py-2.5 text-center">
                    {r.temporal ? (
                      <Clock className="mx-auto h-4 w-4 text-blue-500" />
                    ) : (
                      <Minus className="mx-auto h-4 w-4 text-slate-300 dark:text-slate-600" />
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex flex-col gap-0.5">
                      {pairList.map((p) => (
                        <span key={p} className="text-xs text-slate-500 dark:text-slate-400">
                          {p}
                        </span>
                      ))}
                      {pairList.length === 0 && <span className="text-xs text-slate-400">--</span>}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
