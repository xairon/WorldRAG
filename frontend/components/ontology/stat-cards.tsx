"use client"

import { useEffect, useRef, useState } from "react"
import { Boxes, Link2, Layers, GitBranch } from "lucide-react"

interface StatCardProps {
  label: string
  value: number
  icon: React.ElementType
  color: string
}

function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = useState(0)
  const ref = useRef<number>(0)

  useEffect(() => {
    const duration = 800
    const start = performance.now()
    const from = ref.current

    function tick(now: number) {
      const t = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - t, 3)
      const current = Math.round(from + (value - from) * eased)
      setDisplay(current)
      if (t < 1) requestAnimationFrame(tick)
      else ref.current = value
    }

    requestAnimationFrame(tick)
  }, [value])

  return <span>{display.toLocaleString()}</span>
}

function StatCard({ label, value, icon: Icon, color }: StatCardProps) {
  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900/50">
      <div className={`absolute -right-4 -top-4 h-24 w-24 rounded-full opacity-10 ${color}`} />
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{label}</p>
          <p className="mt-2 text-3xl font-bold tracking-tight text-slate-900 dark:text-white">
            <AnimatedNumber value={value} />
          </p>
        </div>
        <div className={`rounded-lg p-2.5 ${color} bg-opacity-10 dark:bg-opacity-20`}>
          <Icon className="h-5 w-5 text-current" />
        </div>
      </div>
    </div>
  )
}

interface StatCardsProps {
  totalEntities: number
  totalRelations: number
  entityTypes: number
  relationTypes: number
}

export function StatCards({ totalEntities, totalRelations, entityTypes, relationTypes }: StatCardsProps) {
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <StatCard label="Entities" value={totalEntities} icon={Boxes} color="text-blue-500" />
      <StatCard label="Relations" value={totalRelations} icon={Link2} color="text-purple-500" />
      <StatCard label="Entity Types" value={entityTypes} icon={Layers} color="text-emerald-500" />
      <StatCard label="Relation Types" value={relationTypes} icon={GitBranch} color="text-amber-500" />
    </div>
  )
}
