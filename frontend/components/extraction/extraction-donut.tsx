"use client"

import { PieChart, Pie, Cell, Legend, ResponsiveContainer } from "recharts"
import { getEntityHex } from "@/lib/constants"

interface DonutDatum {
  type: string
  count: number
}

interface ExtractionDonutProps {
  data: DonutDatum[]
}

function CustomLegend({ payload }: { payload?: Array<{ value: string; color: string }> }) {
  if (!payload) return null
  return (
    <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 mt-2">
      {payload.map((entry) => (
        <span key={entry.value} className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          <span
            className="inline-block size-2 rounded-full shrink-0"
            style={{ backgroundColor: entry.color }}
          />
          {entry.value}
        </span>
      ))}
    </div>
  )
}

export function ExtractionDonut({ data }: ExtractionDonutProps) {
  const filtered = data.filter((d) => d.count > 0)

  if (filtered.length === 0) {
    return (
      <div className="flex h-[280px] items-center justify-center text-sm text-muted-foreground">
        No entities yet
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie
          data={filtered}
          dataKey="count"
          nameKey="type"
          cx="50%"
          cy="45%"
          innerRadius={60}
          outerRadius={90}
          paddingAngle={2}
          strokeWidth={0}
        >
          {filtered.map((entry) => (
            <Cell key={entry.type} fill={getEntityHex(entry.type)} />
          ))}
        </Pie>
        <Legend content={<CustomLegend />} />
      </PieChart>
    </ResponsiveContainer>
  )
}
