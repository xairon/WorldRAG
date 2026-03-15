import { apiFetch } from "@/lib/api/client"
import { BooksTable } from "@/components/books/books-table"

async function getBooks(slug: string) {
  try {
    return await apiFetch<any[]>(`/projects/${slug}/books`)
  } catch {
    return []
  }
}

export default async function BooksPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const books = await getBooks(slug)
  return <BooksTable slug={slug} books={books} />
}
