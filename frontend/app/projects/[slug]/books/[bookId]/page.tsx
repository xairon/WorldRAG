import { getBookDetail } from "@/lib/api/books"
import type { BookDetail } from "@/lib/api/types"
import { BookDetailHeader } from "@/components/books/book-detail-header"
import { BookDetailTabs } from "@/components/books/book-detail-tabs"
import { notFound } from "next/navigation"

async function fetchBook(bookId: string): Promise<BookDetail | null> {
  try {
    return await getBookDetail(bookId)
  } catch {
    return null
  }
}

export default async function BookDetailPage({
  params,
}: {
  params: Promise<{ slug: string; bookId: string }>
}) {
  const { slug, bookId } = await params
  const data = await fetchBook(bookId)
  if (!data) return notFound()

  const coverUrl = `/api/books/${bookId}/cover`

  return (
    <div className="p-6 max-w-5xl">
      <BookDetailHeader book={data.book} slug={slug} coverUrl={coverUrl} />
      <BookDetailTabs chapters={data.chapters} slug={slug} bookId={bookId} />
    </div>
  )
}
