import { cn } from "@/lib/utils"

interface ConfidenceBarProps {
  value: number
  size?: "sm" | "md"
}

export function ConfidenceBar({ value, size = "md" }: ConfidenceBarProps) {
  const clamped = Math.max(0, Math.min(1, value))
  const pct = Math.round(clamped * 100)

  const colorClass =
    clamped > 0.7
      ? "bg-green-500"
      : clamped >= 0.3
        ? "bg-amber-500"
        : "bg-red-500"

  const heightClass = size === "sm" ? "h-1" : "h-1.5"

  return (
    <div
      className={cn("w-full rounded-full bg-muted overflow-hidden", heightClass)}
      title={`${pct}%`}
      role="meter"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={cn("h-full rounded-full transition-all", colorClass)}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}
