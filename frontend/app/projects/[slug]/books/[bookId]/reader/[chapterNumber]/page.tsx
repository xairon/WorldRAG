import { apiFetch } from "@/lib/api/client"
import type { BookDetail } from "@/lib/api/types"
import { ChapterContent } from "@/components/reader/chapter-content"
import { ReaderNav } from "@/components/reader/reader-nav"
import { ReaderProgress } from "@/components/reader/reader-progress"

interface ChapterText {
  chapter_number: number
  title: string
  text: string
}

async function getChapterText(bookId: string, chapterNumber: string) {
  return apiFetch<ChapterText>(
    `/reader/books/${bookId}/chapters/${chapterNumber}/text`,
  )
}

async function getBookDetail(bookId: string) {
  return apiFetch<BookDetail>(`/books/${bookId}`)
}

export default async function ReaderChapterPage({
  params,
}: {
  params: Promise<{ slug: string; bookId: string; chapterNumber: string }>
}) {
  const { slug, bookId, chapterNumber } = await params
  const [chapter, { book, chapters }] = await Promise.all([
    getChapterText(bookId, chapterNumber),
    getBookDetail(bookId),
  ])

  const current = Number(chapterNumber)
  const prevChapter = chapters.find((c) => c.number === current - 1)
  const nextChapter = chapters.find((c) => c.number === current + 1)

  return (
    <div className="mx-auto max-w-[680px] py-12 px-4 space-y-8">
      <header className="space-y-1">
        <p className="text-sm font-mono text-muted-foreground">
          Chapter {chapter.chapter_number}
        </p>
        <h1 className="text-3xl font-bold">{chapter.title}</h1>
      </header>

      <ChapterContent text={chapter.text} />

      <footer className="space-y-4 border-t pt-6">
        <ReaderProgress current={current} total={book.total_chapters} />
        <ReaderNav
          slug={slug}
          bookId={bookId}
          current={current}
          total={book.total_chapters}
          prevTitle={prevChapter?.title}
          nextTitle={nextChapter?.title}
        />
      </footer>
    </div>
  )
}
