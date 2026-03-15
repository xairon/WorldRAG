import { formatNumber } from "@/lib/utils"

interface ExtractionHeaderProps {
  entities: number
  relations: number
  chaptersDone: number
  chaptersTotal: number
  cost: number
}

function StatCard({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-3xl font-mono font-semibold tabular-nums">
        {value}
      </span>
      <span className="text-xs text-muted-foreground uppercase tracking-wide">
        {label}
      </span>
    </div>
  )
}

export function ExtractionHeader({
  entities,
  relations,
  chaptersDone,
  chaptersTotal,
  cost,
}: ExtractionHeaderProps) {
  const progress = chaptersTotal > 0 ? (chaptersDone / chaptersTotal) * 100 : 0

  return (
    <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
      <StatCard value={formatNumber(entities)} label="Entities" />
      <StatCard value={formatNumber(relations)} label="Relations" />
      <div className="flex flex-col gap-1">
        <span className="text-3xl font-mono font-semibold tabular-nums">
          {formatNumber(chaptersDone)}
          <span className="text-lg text-muted-foreground">
            /{formatNumber(chaptersTotal)}
          </span>
        </span>
        <span className="text-xs text-muted-foreground uppercase tracking-wide">
          Chapters
        </span>
        <div className="mt-1 h-1.5 w-full rounded-full bg-muted overflow-hidden">
          <div
            className="h-full rounded-full bg-primary transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
      <StatCard value={`$${cost.toFixed(2)}`} label="Cost" />
    </div>
  )
}
