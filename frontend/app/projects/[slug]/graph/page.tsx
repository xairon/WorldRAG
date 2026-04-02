"use client"

import { use, useMemo, useCallback } from "react"
import { useQueryState, parseAsString } from "nuqs"
import { Loader2 } from "lucide-react"
import { useBooks } from "@/hooks/use-books"
import { GraphContainer } from "@/components/graph/graph-container"
import { EmptyState } from "@/components/shared/empty-state"

export default function GraphPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = use(params)
  const [bookId, setBookId] = useQueryState("book", parseAsString)
  const { data: booksRaw, isLoading } = useBooks(slug)

  const books = useMemo(() => {
    if (!booksRaw) return []
    return (booksRaw as Array<Record<string, unknown>>).map((b) => ({
      id: (b.book_id as string) ?? (b.id as string) ?? "",
      title:
        (b.original_filename as string) ?? (b.title as string) ?? "Book",
    }))
  }, [booksRaw])

  // Auto-select first book if none selected
  const effectiveBookId = bookId ?? books[0]?.id ?? null

  const handleBookChange = useCallback(
    (id: string) => setBookId(id),
    [setBookId],
  )

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (books.length === 0) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
        <EmptyState
          title="No books in this project"
          description="Upload and extract a book to explore its Knowledge Graph."
        />
      </div>
    )
  }

  if (!effectiveBookId) return null

  return (
    <div className="h-[calc(100vh-4rem)]">
      <GraphContainer
        projectSlug={slug}
        bookId={effectiveBookId}
        books={books}
        onBookChange={handleBookChange}
      />
    </div>
  )
}
