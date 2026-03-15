import { apiFetch } from "@/lib/api/client"
import { ExtractionDashboard } from "./dashboard"

async function getBookDetail(bookId: string) {
  try {
    return await apiFetch<{
      book: { id: string; title: string; total_chapters: number; status: string; total_cost_usd: number }
      chapters: Array<{
        number: number
        title: string
        words: number
        entity_count: number
        status: string
        entities: { type: string; count: number }[]
      }>
    }>(`/books/${bookId}`)
  } catch {
    return {
      book: { id: bookId, title: "Unknown", total_chapters: 0, status: "pending", total_cost_usd: 0 },
      chapters: [],
    }
  }
}

async function getProjectInfo(slug: string) {
  try {
    return await apiFetch<{ has_profile: boolean; books_count: number }>(`/projects/${slug}/stats`)
  } catch {
    return { has_profile: false, books_count: 1 }
  }
}

export default async function ExtractionPage({
  params,
}: {
  params: Promise<{ slug: string; bookId: string }>
}) {
  const { slug, bookId } = await params
  const [detail, stats] = await Promise.all([getBookDetail(bookId), getProjectInfo(slug)])

  return (
    <ExtractionDashboard
      slug={slug}
      bookId={bookId}
      book={detail.book}
      chapters={detail.chapters}
      hasProfile={stats.has_profile ?? false}
      isFirstBook={(stats.books_count ?? 1) <= 1}
    />
  )
}
