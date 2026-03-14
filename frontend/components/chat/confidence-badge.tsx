interface ConfidenceBadgeProps {
  score: number
}

export function ConfidenceBadge({ score }: ConfidenceBadgeProps) {
  let color: string
  let label: string

  if (score >= 0.8) {
    color = "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
    label = "High confidence"
  } else if (score >= 0.5) {
    color = "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400"
    label = "Medium confidence"
  } else {
    color = "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
    label = "Low confidence"
  }

  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${color}`}
      title={`Faithfulness score: ${(score * 100).toFixed(0)}%`}
    >
      {label}
    </span>
  )
}
