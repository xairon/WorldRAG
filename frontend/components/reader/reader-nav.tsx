"use client"

import Link from "next/link"
import { ChevronLeft, ChevronRight } from "lucide-react"

interface ReaderNavProps {
  slug: string
  bookId: string
  current: number
  total: number
  prevTitle?: string
  nextTitle?: string
}

export function ReaderNav({
  slug,
  bookId,
  current,
  total,
  prevTitle,
  nextTitle,
}: ReaderNavProps) {
  const hasPrev = current > 1
  const hasNext = current < total

  return (
    <div className="flex items-center justify-between">
      {hasPrev ? (
        <Link
          href={`/projects/${slug}/books/${bookId}/reader/${current - 1}`}
          className="flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ChevronLeft className="h-4 w-4" />
          {prevTitle ? <span>{prevTitle}</span> : <span>Previous</span>}
        </Link>
      ) : (
        <div />
      )}

      {hasNext ? (
        <Link
          href={`/projects/${slug}/books/${bookId}/reader/${current + 1}`}
          className="flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          {nextTitle ? <span>{nextTitle}</span> : <span>Next</span>}
          <ChevronRight className="h-4 w-4" />
        </Link>
      ) : (
        <div />
      )}
    </div>
  )
}
