"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, BookOpen, Loader2 } from "lucide-react"
import { getChapterText, getChapterEntities, getChapterParagraphs } from "@/lib/api/reader"
import { getBook } from "@/lib/api/books"
import type { ChapterText, ChapterEntities, ChapterParagraphs } from "@/lib/api/reader"
import type { ChapterInfo } from "@/lib/api/types"
import { AnnotatedText } from "@/components/reader/annotated-text"
import { ParagraphRenderer } from "@/components/reader/paragraph-renderer"
import { ChapterNav } from "@/components/reader/chapter-nav"
import { ReadingToolbar } from "@/components/reader/reading-toolbar"
import { Skeleton } from "@/components/ui/skeleton"
import { ScrollArea } from "@/components/ui/scroll-area"

type ReadingMode = "annotated" | "clean" | "focus"

export default function ReaderPage() {
  const params = useParams()
  const bookId = params.bookId as string
  const chapterNum = parseInt(params.chapter as string, 10)

  const [chapterText, setChapterText] = useState<ChapterText | null>(null)
  const [chapterEntities, setChapterEntities] = useState<ChapterEntities | null>(null)
  const [chapterParagraphs, setChapterParagraphs] = useState<ChapterParagraphs | null>(null)
  const [chapters, setChapters] = useState<ChapterInfo[]>([])
  const [bookTitle, setBookTitle] = useState("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<ReadingMode>("annotated")
  const [focusType, setFocusType] = useState<string | undefined>(undefined)

  useEffect(() => {
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [text, entities, paragraphs, bookDetail] = await Promise.allSettled([
          getChapterText(bookId, chapterNum),
          getChapterEntities(bookId, chapterNum),
          getChapterParagraphs(bookId, chapterNum),
          getBook(bookId),
        ])

        if (text.status === "fulfilled") setChapterText(text.value)
        else setError("Failed to load chapter text")

        if (entities.status === "fulfilled") setChapterEntities(entities.value)
        if (paragraphs.status === "fulfilled") setChapterParagraphs(paragraphs.value)

        if (bookDetail.status === "fulfilled") {
          setBookTitle(bookDetail.value.book.title)
          setChapters(bookDetail.value.chapters)
        }
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [bookId, chapterNum])

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-6 w-48" />
        <div className="space-y-3">
          {Array.from({ length: 12 }).map((_, i) => (
            <Skeleton key={i} className="h-4 w-full" />
          ))}
        </div>
      </div>
    )
  }

  if (error || !chapterText) {
    return (
      <div className="max-w-4xl mx-auto space-y-4">
        <Link
          href={`/library/${bookId}`}
          className="text-sm text-slate-500 hover:text-slate-300 flex items-center gap-1"
        >
          <ArrowLeft className="h-3 w-3" /> Back to book
        </Link>
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-8 text-center">
          <p className="text-red-400">{error ?? "Chapter not found"}</p>
        </div>
      </div>
    )
  }

  const annotations = chapterEntities?.annotations ?? []
  const paragraphs = chapterParagraphs?.paragraphs ?? []
  const hasParagraphs = paragraphs.length > 0

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Link href="/library" className="hover:text-slate-300 transition-colors">Library</Link>
        <span>/</span>
        <Link href={`/library/${bookId}`} className="hover:text-slate-300 transition-colors truncate max-w-[200px]">
          {bookTitle || "Book"}
        </Link>
        <span>/</span>
        <span className="text-slate-400">Ch. {chapterNum}</span>
      </div>

      {/* Chapter header */}
      <div>
        <div className="flex items-center gap-3 mb-1">
          <BookOpen className="h-5 w-5 text-indigo-400" />
          <h1 className="text-2xl font-bold tracking-tight">{chapterText.title}</h1>
        </div>
        <p className="text-xs text-slate-500">
          {chapterText.word_count.toLocaleString()} words
          {annotations.length > 0 && ` \u00b7 ${annotations.length} entity mentions`}
        </p>
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <ReadingToolbar
          mode={mode}
          focusType={focusType}
          onModeChange={setMode}
          onFocusTypeChange={setFocusType}
          annotationCount={annotations.length}
        />
      </div>

      {/* Chapter content */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-6 md:p-10">
        {hasParagraphs ? (
          // V2: Paragraph-by-paragraph rendering with type styling
          <div>
            {paragraphs.map((para) => (
              <ParagraphRenderer key={para.index} paragraph={para}>
                <AnnotatedText
                  text={para.text}
                  annotations={annotations.filter(
                    (a) => a.char_offset_start >= para.char_start && a.char_offset_end <= para.char_end
                  ).map((a) => ({
                    ...a,
                    char_offset_start: a.char_offset_start - para.char_start,
                    char_offset_end: a.char_offset_end - para.char_start,
                  }))}
                  mode={mode}
                  focusType={focusType}
                />
              </ParagraphRenderer>
            ))}
          </div>
        ) : (
          // V1 fallback: Monolithic text rendering
          <AnnotatedText
            text={chapterText.text}
            annotations={annotations}
            mode={mode}
            focusType={focusType}
          />
        )}
      </div>

      {/* Chapter navigation */}
      {chapters.length > 0 && (
        <div className="border-t border-slate-800 pt-4">
          <ChapterNav bookId={bookId} currentChapter={chapterNum} chapters={chapters} />
        </div>
      )}
    </div>
  )
}
