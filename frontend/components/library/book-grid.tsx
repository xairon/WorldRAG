"use client"

import { BookCard, type LibraryBook } from "./book-card"
export type { LibraryBook }
import { UploadCard } from "./upload-card"
import { EmptyState } from "@/components/shared/empty-state"
import { Upload } from "lucide-react"

export function BookGrid({ slug, books }: { slug: string; books: LibraryBook[] }) {
  if (books.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <EmptyState
          title="Drop your first book here"
          description="Supports EPUB, PDF, TXT"
          icon={<Upload className="h-12 w-12 text-muted-foreground" />}
        />
        <div className="mt-8 w-64">
          <UploadCard slug={slug} />
        </div>
      </div>
    )
  }

  return (
    <div className="grid gap-4 grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
      {books.map((book) => (
        <BookCard key={book.id} book={book} slug={slug} />
      ))}
      <UploadCard slug={slug} />
    </div>
  )
}
