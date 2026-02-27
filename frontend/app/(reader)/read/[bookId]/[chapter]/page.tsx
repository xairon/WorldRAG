"use client"

import { useEffect, useMemo, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, BookOpen } from "lucide-react"
import { getChapterText, getChapterEntities, getChapterParagraphs } from "@/lib/api/reader"
import { getBook } from "@/lib/api/books"
import type { ChapterText, ChapterEntities, ChapterParagraphs } from "@/lib/api/reader"
import type { ChapterInfo } from "@/lib/api/types"
import { LABEL_COLORS } from "@/lib/utils"
import { AnnotatedText } from "@/components/reader/annotated-text"
import { AnnotationSidebar } from "@/components/reader/annotation-sidebar"
import { ParagraphRenderer } from "@/components/reader/paragraph-renderer"
import { ChapterNav } from "@/components/reader/chapter-nav"
import { ReadingToolbar } from "@/components/reader/reading-toolbar"
import { Skeleton } from "@/components/ui/skeleton"

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
  const [enabledTypes, setEnabledTypes] = useState<Set<string>>(new Set(Object.keys(LABEL_COLORS)))

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

  // All hooks MUST be above early returns (Rules of Hooks)
  const annotations = chapterEntities?.annotations ?? []
  const paragraphs = chapterParagraphs?.paragraphs ?? []

  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const a of annotations) {
      counts[a.entity_type] = (counts[a.entity_type] ?? 0) + 1
    }
    return counts
  }, [annotations])

  const filteredAnnotations = useMemo(() => {
    if (mode === "clean") return []
    return annotations.filter((a) => enabledTypes.has(a.entity_type))
  }, [annotations, enabledTypes, mode])

  const paragraphAnnotations = useMemo(() => {
    const map = new Map<number, typeof filteredAnnotations>()
    for (const para of paragraphs) {
      const paraAnns = filteredAnnotations
        .filter((a) => a.char_offset_start >= para.char_start && a.char_offset_end <= para.char_end)
        .map((a) => ({
          ...a,
          char_offset_start: a.char_offset_start - para.char_start,
          char_offset_end: a.char_offset_end - para.char_start,
        }))
      map.set(para.index, paraAnns)
    }
    return map
  }, [paragraphs, filteredAnnotations])

  const handleToggleType = (type: string) => {
    setEnabledTypes((prev) => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

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

  const hasParagraphs = paragraphs.length > 0

  return (
    <div className="max-w-5xl mx-auto space-y-6">
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
          enabledTypes={enabledTypes}
          onModeChange={setMode}
          onToggleType={handleToggleType}
          annotationCount={filteredAnnotations.length}
          typeCounts={typeCounts}
        />
      </div>

      {/* Chapter content */}
      <div className="flex gap-6">
        {/* Main content */}
        <div className="flex-1 rounded-xl border border-slate-800 bg-slate-900/30 p-6 md:p-10">
          {hasParagraphs ? (
            // V2: Paragraph-by-paragraph rendering with type styling
            <div>
              {paragraphs.map((para) => (
                <ParagraphRenderer key={para.index} paragraph={para}>
                  <AnnotatedText
                    text={para.text}
                    annotations={paragraphAnnotations.get(para.index) ?? []}
                    mode={mode}
                  />
                </ParagraphRenderer>
              ))}
            </div>
          ) : (
            // V1 fallback: Monolithic text rendering
            <AnnotatedText
              text={chapterText.text}
              annotations={filteredAnnotations}
              mode={mode}
            />
          )}
        </div>

        {/* Sidebar */}
        {mode !== "clean" && filteredAnnotations.length > 0 && (
          <div className="hidden lg:block w-56 shrink-0">
            <AnnotationSidebar annotations={filteredAnnotations} className="sticky top-6" />
          </div>
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
