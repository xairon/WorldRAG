"use client"

import Link from "next/link"
import { Button } from "@/components/ui/button"
import { BookStatusBadge } from "@/components/books/book-status-badge"
import { BookOpen, Network, Play, RotateCcw } from "lucide-react"
import { formatNumber } from "@/lib/utils"
import type { BookInfo } from "@/lib/api/types"

interface BookDetailHeaderProps {
  book: BookInfo
  slug: string
  coverUrl?: string | null
}

export function BookDetailHeader({ book, slug, coverUrl }: BookDetailHeaderProps) {
  const canExtract = ["ready", "completed"].includes(book.status)
  const isExtracted = ["extracted", "embedded", "done"].includes(book.status)

  return (
    <div className="flex flex-col md:flex-row gap-6">
      <div className="w-48 md:w-56 shrink-0">
        {coverUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={coverUrl}
            alt={book.title}
            className="w-full aspect-[2/3] object-cover rounded-lg shadow-lg"
          />
        ) : (
          <div className="w-full aspect-[2/3] rounded-lg bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center shadow-lg">
            <span className="text-5xl font-display font-bold text-primary/30">
              {book.title.charAt(0).toUpperCase()}
            </span>
          </div>
        )}
      </div>

      <div className="flex-1 min-w-0">
        <h1 className="text-3xl font-display font-bold tracking-tight">{book.title}</h1>
        {book.author && (
          <p className="text-lg text-muted-foreground mt-1">{book.author}</p>
        )}

        <div className="mt-4">
          <BookStatusBadge status={book.status} />
        </div>

        <div className="grid grid-cols-2 gap-4 mt-6 text-sm">
          <div>
            <span className="text-muted-foreground">Chapters</span>
            <p className="font-semibold tabular-nums">{formatNumber(book.total_chapters)}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Processed</span>
            <p className="font-semibold tabular-nums">{book.chapters_processed} / {book.total_chapters}</p>
          </div>
          {book.series_name && (
            <div>
              <span className="text-muted-foreground">Series</span>
              <p className="font-semibold">{book.series_name}</p>
            </div>
          )}
          {book.order_in_series != null && (
            <div>
              <span className="text-muted-foreground">Volume</span>
              <p className="font-semibold">#{book.order_in_series}</p>
            </div>
          )}
        </div>

        <div className="flex flex-wrap gap-3 mt-6">
          {canExtract && !isExtracted && (
            <Link href={`/projects/${slug}/books/${book.id}/extraction`}>
              <Button><Play className="h-4 w-4 mr-2" /> Extract entities</Button>
            </Link>
          )}
          <Link href={`/projects/${slug}/books/${book.id}/reader/1`}>
            <Button variant="secondary"><BookOpen className="h-4 w-4 mr-2" /> Open reader</Button>
          </Link>
          <Link href={`/projects/${slug}/graph`}>
            <Button variant="secondary"><Network className="h-4 w-4 mr-2" /> View in graph</Button>
          </Link>
          {isExtracted && (
            <Link href={`/projects/${slug}/books/${book.id}/extraction`}>
              <Button variant="ghost"><RotateCcw className="h-4 w-4 mr-2" /> Re-extract</Button>
            </Link>
          )}
        </div>
      </div>
    </div>
  )
}
