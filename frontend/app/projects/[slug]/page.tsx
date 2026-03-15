import { apiFetch } from "@/lib/api/client"
import { BookGrid, type LibraryBook } from "@/components/library/book-grid"

async function getBooks(slug: string): Promise<LibraryBook[]> {
  try {
    return await apiFetch<LibraryBook[]>(`/projects/${slug}/books`)
  } catch {
    return []
  }
}

export default async function LibraryPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const books = await getBooks(slug)

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-display font-semibold tracking-tight">Library</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {books.length} book{books.length !== 1 ? "s" : ""}
          </p>
        </div>
      </div>
      <BookGrid slug={slug} books={books} />
    </div>
  )
}
