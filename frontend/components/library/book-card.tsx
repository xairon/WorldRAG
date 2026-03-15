"use client"

import Link from "next/link"
import { cn } from "@/lib/utils"
import { BookStatusBadge } from "@/components/books/book-status-badge"

export interface LibraryBook {
  id: string
  book_id?: string | null
  original_filename?: string
  filename?: string
  book_num: number
  status?: string
  total_chapters?: number
  total_words?: number
  cover_image?: string | null
  author?: string | null
  title?: string | null
}

function displayTitle(book: LibraryBook): string {
  if (book.title) return book.title
  return (book.original_filename ?? book.filename ?? "Untitled")
    .replace(/\.(epub|pdf|txt)$/i, "")
    .replace(/ -- .*/g, "")
}

export function BookCard({ book, slug }: { book: LibraryBook; slug: string }) {
  const href = book.book_id ? `/projects/${slug}/books/${book.book_id}` : undefined
  const name = displayTitle(book)
  const status = book.status ?? "pending"

  const card = (
    <div
      className={cn(
        "group relative rounded-xl border overflow-hidden transition-all duration-150",
        href && "hover:scale-[1.02] hover:shadow-lg cursor-pointer",
        !href && "opacity-60",
      )}
    >
      <div className="aspect-[2/3] overflow-hidden bg-muted relative">
        {book.cover_image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={book.cover_image} alt="" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center">
            <span className="text-3xl font-display font-bold text-primary/30">
              {name.charAt(0).toUpperCase()}
            </span>
          </div>
        )}
        <div className="absolute bottom-2 right-2">
          <BookStatusBadge status={status} />
        </div>
      </div>
      <div className="p-3">
        <h3 className="font-semibold text-sm line-clamp-2 leading-tight">{name}</h3>
        {book.author && (
          <p className="text-xs text-muted-foreground mt-1 truncate">{book.author}</p>
        )}
      </div>
    </div>
  )

  if (href) {
    return <Link href={href}>{card}</Link>
  }
  return card
}
