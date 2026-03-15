import { redirect } from "next/navigation"

export default async function ReaderIndexPage({
  params,
}: {
  params: Promise<{ slug: string; bookId: string }>
}) {
  const { slug, bookId } = await params
  redirect(`/projects/${slug}/books/${bookId}/reader/1`)
}
