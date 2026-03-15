interface ReaderProgressProps {
  current: number
  total: number
}

export function ReaderProgress({ current, total }: ReaderProgressProps) {
  const percentage = total > 0 ? Math.round((current / total) * 100) : 0

  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-muted-foreground font-mono">
        {current} / {total}
      </span>
      <div className="flex-1 h-1 bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-foreground/20 rounded-full transition-all duration-300"
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-xs text-muted-foreground font-mono">
        {percentage}%
      </span>
    </div>
  )
}
