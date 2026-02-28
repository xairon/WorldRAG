"use client"

import { useEffect, useMemo, useState } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { ArrowLeft } from "lucide-react"
import { getChapterText, getChapterEntities, getChapterParagraphs, getChapterXHTML } from "@/lib/api/reader"
import { getBook } from "@/lib/api/books"
import type { ChapterText, ChapterEntities, ChapterParagraphs, ChapterXHTML } from "@/lib/api/reader"
import type { ChapterInfo } from "@/lib/api/types"
import { LABEL_COLORS } from "@/lib/utils"
import { AnnotatedText } from "@/components/reader/annotated-text"
import { ParagraphRenderer } from "@/components/reader/paragraph-renderer"
import { EpubRenderer } from "@/components/reader/epub-renderer"
import { ReaderToolbar } from "@/components/reader/reader-toolbar"
import { useReaderSettings, THEME_STYLES } from "@/hooks/use-reader-settings"

export default function ReaderPage() {
  const params = useParams()
  const bookId = params.bookId as string
  const chapterNum = parseInt(params.chapter as string, 10)

  const [chapterText, setChapterText] = useState<ChapterText | null>(null)
  const [chapterEntities, setChapterEntities] = useState<ChapterEntities | null>(null)
  const [chapterParagraphs, setChapterParagraphs] = useState<ChapterParagraphs | null>(null)
  const [chapterXHTML, setChapterXHTML] = useState<ChapterXHTML | null>(null)
  const [chapters, setChapters] = useState<ChapterInfo[]>([])
  const [bookTitle, setBookTitle] = useState("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [enabledTypes, setEnabledTypes] = useState<Set<string>>(new Set(Object.keys(LABEL_COLORS)))

  const {
    settings,
    update,
    theme: t,
    loaded,
    increaseFontSize,
    decreaseFontSize,
    cycleLineHeight,
  } = useReaderSettings()

  useEffect(() => {
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [text, entities, paragraphs, xhtml, bookDetail] = await Promise.allSettled([
          getChapterText(bookId, chapterNum),
          getChapterEntities(bookId, chapterNum),
          getChapterParagraphs(bookId, chapterNum),
          getChapterXHTML(bookId, chapterNum),
          getBook(bookId),
        ])

        if (text.status === "fulfilled") setChapterText(text.value)
        else setError("Failed to load chapter text")

        if (entities.status === "fulfilled") setChapterEntities(entities.value)
        if (paragraphs.status === "fulfilled") setChapterParagraphs(paragraphs.value)
        if (xhtml.status === "fulfilled") setChapterXHTML(xhtml.value)
        else setChapterXHTML(null)

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

  // Scroll to top on chapter change
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" })
  }, [chapterNum])

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
    if (!settings.annotations) return []
    return annotations.filter((a) => enabledTypes.has(a.entity_type))
  }, [annotations, enabledTypes, settings.annotations])

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

  const hasXHTML = !!chapterXHTML?.xhtml
  const hasParagraphs = paragraphs.length > 0
  const mode = settings.annotations ? "annotated" : "clean"

  // Title from best available source
  const displayTitle = chapterXHTML?.title || chapterText?.title || `Chapter ${chapterNum}`
  const wordCount = chapterXHTML?.word_count || chapterText?.word_count || 0

  // Don't render until settings loaded from localStorage (avoids theme flash)
  if (!loaded) return null

  if (loading) {
    return (
      <div
        className="fixed inset-0 z-50 overflow-y-auto transition-colors duration-300"
        style={{ backgroundColor: t.bg }}
      >
        <div className="max-w-[680px] mx-auto pt-20 px-6 space-y-4">
          {Array.from({ length: 16 }).map((_, i) => (
            <div
              key={i}
              className="h-4 rounded animate-pulse"
              style={{
                backgroundColor: t.surface,
                width: i === 0 ? "40%" : i === 15 ? "60%" : "100%",
              }}
            />
          ))}
        </div>
      </div>
    )
  }

  if (error || (!chapterText && !chapterXHTML)) {
    return (
      <div className="fixed inset-0 z-50 overflow-y-auto" style={{ backgroundColor: t.bg }}>
        <div className="max-w-[680px] mx-auto pt-20 px-6">
          <Link
            href={`/library/${bookId}`}
            className="text-sm flex items-center gap-1 mb-6"
            style={{ color: t.textMuted }}
          >
            <ArrowLeft className="h-3 w-3" /> Back to book
          </Link>
          <div
            className="rounded-lg p-8 text-center"
            style={{ backgroundColor: t.surface, color: "#ef4444" }}
          >
            <p>{error ?? "Chapter not found"}</p>
          </div>
        </div>
      </div>
    )
  }

  const font =
    settings.fontFamily === "serif"
      ? '"Literata", "Georgia", "Cambria", "Times New Roman", serif'
      : '"Inter", system-ui, -apple-system, sans-serif'

  return (
    <div
      className="fixed inset-0 z-50 overflow-y-auto transition-colors duration-300"
      style={{ backgroundColor: t.bg }}
    >
      {/* Toolbar */}
      {chapters.length > 0 && (
        <ReaderToolbar
          bookId={bookId}
          currentChapter={chapterNum}
          chapters={chapters}
          settings={settings}
          onUpdate={update}
          onIncreaseFontSize={increaseFontSize}
          onDecreaseFontSize={decreaseFontSize}
          onCycleLineHeight={cycleLineHeight}
          enabledTypes={enabledTypes}
          onToggleType={handleToggleType}
          typeCounts={typeCounts}
        />
      )}

      {/* Reading area */}
      <div className="max-w-[680px] mx-auto px-6 md:px-10">
        {/* Chapter header */}
        <div className="pt-12 pb-8 text-center">
          {/* Book title breadcrumb */}
          <Link
            href={`/library/${bookId}`}
            className="text-[11px] uppercase tracking-[0.15em] transition-colors hover:opacity-80"
            style={{ color: t.textMuted }}
          >
            {bookTitle || "Book"}
          </Link>

          <h1
            className="mt-4 font-semibold tracking-tight"
            style={{
              fontSize: `${Math.round(settings.fontSize * 1.5)}px`,
              lineHeight: 1.3,
              color: t.heading,
              fontFamily: font,
            }}
          >
            {displayTitle}
          </h1>

          {/* Subtle divider */}
          <div
            className="mx-auto mt-6 mb-2 w-12 h-px"
            style={{ backgroundColor: t.border }}
          />

          <p className="text-[11px]" style={{ color: t.textMuted }}>
            {wordCount.toLocaleString()} words
            {filteredAnnotations.length > 0 && (
              <span> &middot; {filteredAnnotations.length} annotations</span>
            )}
          </p>
        </div>

        {/* Chapter content — Priority: XHTML > Paragraphs > Monolithic text */}
        <div className="pb-20">
          {hasXHTML ? (
            /* Epub-quality rendering from original XHTML */
            <EpubRenderer
              xhtml={chapterXHTML!.xhtml}
              css={chapterXHTML!.css}
              annotations={filteredAnnotations}
              showAnnotations={settings.annotations}
              theme={settings.theme}
              fontSize={settings.fontSize}
              lineHeight={settings.lineHeight}
              fontFamily={settings.fontFamily}
              bookId={bookId}
              chapter={chapterNum}
            />
          ) : hasParagraphs ? (
            /* Structured paragraph rendering */
            <div>
              {paragraphs.map((para) => (
                <ParagraphRenderer
                  key={para.index}
                  paragraph={para}
                  theme={settings.theme}
                  fontSize={settings.fontSize}
                  lineHeight={settings.lineHeight}
                  fontFamily={settings.fontFamily}
                >
                  <AnnotatedText
                    text={para.text}
                    annotations={paragraphAnnotations.get(para.index) ?? []}
                    mode={mode}
                    bookId={bookId}
                    chapter={chapterNum}
                    theme={settings.theme}
                  />
                </ParagraphRenderer>
              ))}
            </div>
          ) : (
            /* V1 fallback: Monolithic text rendering */
            <div
              style={{
                fontSize: `${settings.fontSize}px`,
                lineHeight: settings.lineHeight,
                color: t.text,
                fontFamily: font,
                whiteSpace: "pre-wrap",
              }}
            >
              {chapterText && (
                <AnnotatedText
                  text={chapterText.text}
                  annotations={filteredAnnotations}
                  mode={mode}
                  bookId={bookId}
                  chapter={chapterNum}
                  theme={settings.theme}
                />
              )}
            </div>
          )}
        </div>

        {/* Chapter navigation footer */}
        {chapters.length > 0 && (
          <div
            className="border-t py-8 flex items-center justify-between"
            style={{ borderColor: t.border }}
          >
            {(() => {
              const prev = chapters
                .filter((c) => c.number < chapterNum)
                .sort((a, b) => b.number - a.number)[0]
              const next = chapters
                .filter((c) => c.number > chapterNum)
                .sort((a, b) => a.number - b.number)[0]
              return (
                <>
                  {prev ? (
                    <Link
                      href={`/read/${bookId}/${prev.number}`}
                      className="group flex flex-col items-start gap-0.5 transition-opacity hover:opacity-80"
                    >
                      <span className="text-[10px] uppercase tracking-wider" style={{ color: t.textMuted }}>
                        Previous
                      </span>
                      <span className="text-sm font-medium" style={{ color: t.text }}>
                        Ch. {prev.number}{prev.title ? ` \u2014 ${prev.title}` : ""}
                      </span>
                    </Link>
                  ) : (
                    <div />
                  )}
                  {next ? (
                    <Link
                      href={`/read/${bookId}/${next.number}`}
                      className="group flex flex-col items-end gap-0.5 transition-opacity hover:opacity-80"
                    >
                      <span className="text-[10px] uppercase tracking-wider" style={{ color: t.textMuted }}>
                        Next
                      </span>
                      <span className="text-sm font-medium" style={{ color: t.text }}>
                        Ch. {next.number}{next.title ? ` \u2014 ${next.title}` : ""}
                      </span>
                    </Link>
                  ) : (
                    <div />
                  )}
                </>
              )
            })()}
          </div>
        )}
      </div>
    </div>
  )
}
