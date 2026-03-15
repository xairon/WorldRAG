import Link from "next/link"
import { apiFetch } from "@/lib/api/client"
import type { BookDetail } from "@/lib/api/types"

async function getBookDetail(bookId: string) {
  return apiFetch<BookDetail>(`/books/${bookId}`)
}

export default async function ChaptersPage({
  params,
}: {
  params: Promise<{ slug: string; bookId: string }>
}) {
  const { slug, bookId } = await params
  const { book, chapters } = await getBookDetail(bookId)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{book.title}</h1>
        <p className="text-sm text-muted-foreground">
          {book.total_chapters} chapters
          {book.author ? ` — ${book.author}` : ""}
        </p>
      </div>

      <div className="rounded-md border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-4 py-3 text-left font-medium">#</th>
              <th className="px-4 py-3 text-left font-medium">Title</th>
              <th className="px-4 py-3 text-right font-medium">Words</th>
              <th className="px-4 py-3 text-right font-medium">Status</th>
              <th className="px-4 py-3 text-right font-medium" />
            </tr>
          </thead>
          <tbody>
            {chapters.map((ch) => (
              <tr key={ch.number} className="border-b last:border-0">
                <td className="px-4 py-3 font-mono text-muted-foreground">
                  {ch.number}
                </td>
                <td className="px-4 py-3">{ch.title}</td>
                <td className="px-4 py-3 text-right font-mono">
                  {ch.word_count.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-right">
                  <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs">
                    {ch.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <Link
                    href={`/projects/${slug}/books/${bookId}/reader/${ch.number}`}
                    className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                  >
                    Read
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
