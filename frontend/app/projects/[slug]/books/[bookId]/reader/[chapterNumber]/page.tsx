import { apiFetch } from "@/lib/api/client"
import type { BookDetail } from "@/lib/api/types"
import { EpubReaderClient } from "./client"
import { ReaderNav } from "@/components/reader/reader-nav"
import { ReaderProgress } from "@/components/reader/reader-progress"

interface ChapterXHTML {
  book_id: string
  chapter_number: number
  title: string
  xhtml: string
  css: string
  word_count: number
}

interface ChapterText {
  book_id: string
  chapter_number: number
  title: string
  text: string
  word_count: number
}

async function getChapterXHTML(bookId: string, chapterNumber: string): Promise<ChapterXHTML | null> {
  try {
    return await apiFetch<ChapterXHTML>(
      `/reader/books/${bookId}/chapters/${chapterNumber}/xhtml`,
    )
  } catch {
    return null
  }
}

async function getChapterText(bookId: string, chapterNumber: string): Promise<ChapterText> {
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
  const [xhtmlData, textData, { book, chapters }] = await Promise.all([
    getChapterXHTML(bookId, chapterNumber),
    getChapterText(bookId, chapterNumber),
    getBookDetail(bookId),
  ])

  const current = Number(chapterNumber)
  const prevChapter = chapters.find((c) => c.number === current - 1)
  const nextChapter = chapters.find((c) => c.number === current + 1)

  // Use XHTML if available (preserves epub formatting), fallback to plain text
  const hasXHTML = xhtmlData?.xhtml && xhtmlData.xhtml.length > 0
  const title = xhtmlData?.title || textData.title

  return (
    <div className="mx-auto max-w-[680px] py-12 px-4 space-y-8">
      <header className="space-y-1">
        <p className="text-sm font-mono text-muted-foreground">
          Chapter {current}
        </p>
        {title && <h1 className="text-3xl font-bold">{title}</h1>}
      </header>

      {hasXHTML ? (
        <EpubReaderClient xhtml={xhtmlData!.xhtml} css={xhtmlData!.css || ""} />
      ) : (
        <div className="space-y-6">
          {textData.text.split(/\n\n+/).filter(Boolean).map((p, i) => (
            <p key={i} className="font-serif text-lg leading-relaxed">{p}</p>
          ))}
        </div>
      )}

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
