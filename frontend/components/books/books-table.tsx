"use client"

import { useRouter } from "next/navigation"
import { formatNumber } from "@/lib/utils"
import { EmptyState } from "@/components/shared/empty-state"
import { BookStatusBadge } from "./book-status-badge"
import { UploadDropZone } from "./upload-drop-zone"

export interface Book {
  id: string
  book_id?: string | null
  original_filename?: string
  filename?: string
  book_num: number
  status?: string
  total_chapters?: number
  total_words?: number
}

export function BooksTable({ slug, books }: { slug: string; books: Book[] }) {
  const router = useRouter()
  const refresh = () => router.refresh()

  if (books.length === 0) {
    return (
      <div className="space-y-6">
        <EmptyState
          title="No books yet"
          description="Upload an EPUB, PDF, or TXT file to get started."
        />
        <UploadDropZone slug={slug} onUploadComplete={refresh} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50 text-left text-xs font-medium text-muted-foreground">
              <th className="px-4 py-3 w-12">#</th>
              <th className="px-4 py-3">Title</th>
              <th className="px-4 py-3 w-24 text-right">Chapters</th>
              <th className="px-4 py-3 w-24 text-right">Words</th>
              <th className="px-4 py-3 w-32">Status</th>
            </tr>
          </thead>
          <tbody>
            {books.map((book) => {
              const hasNeoId = book.book_id != null
              const displayName = (book.original_filename ?? book.filename ?? "Untitled")
                .replace(/\.(epub|pdf|txt)$/i, "")
                .replace(/ -- .*/g, "") // strip "-- Author -- Year" suffixes
              return (
              <tr
                key={book.id}
                onClick={() => hasNeoId && router.push(`/projects/${slug}/books/${book.book_id}/chapters`)}
                className={hasNeoId ? "cursor-pointer border-b transition-colors hover:bg-muted/30" : "border-b opacity-60"}
              >
                <td className="px-4 py-3 font-mono text-muted-foreground">{book.book_num}</td>
                <td className="px-4 py-3 font-medium">{displayName}</td>
                <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                  {book.total_chapters != null ? formatNumber(book.total_chapters) : "\u2014"}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                  {book.total_words != null ? formatNumber(book.total_words) : "\u2014"}
                </td>
                <td className="px-4 py-3">
                  <BookStatusBadge status={book.status ?? "pending"} />
                </td>
              </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <UploadDropZone slug={slug} onUploadComplete={refresh} />
    </div>
  )
}
