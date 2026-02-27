"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { ChevronLeft, ChevronRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { ChapterInfo } from "@/lib/api/types"

interface ChapterNavProps {
  bookId: string
  currentChapter: number
  chapters: ChapterInfo[]
}

export function ChapterNav({ bookId, currentChapter, chapters }: ChapterNavProps) {
  const router = useRouter()
  const hasPrev = currentChapter > 1
  const hasNext = chapters.some((c) => c.number > currentChapter)
  const prevChapter = chapters
    .filter((c) => c.number < currentChapter)
    .sort((a, b) => b.number - a.number)[0]
  const nextChapter = chapters
    .filter((c) => c.number > currentChapter)
    .sort((a, b) => a.number - b.number)[0]

  return (
    <div className="flex items-center justify-between">
      {hasPrev && prevChapter ? (
        <Button variant="outline" size="sm" asChild>
          <Link href={`/read/${bookId}/${prevChapter.number}`}>
            <ChevronLeft className="h-4 w-4 mr-1" />
            Ch. {prevChapter.number}
          </Link>
        </Button>
      ) : (
        <div />
      )}

      {/* Chapter selector */}
      <select
        aria-label="Select chapter"
        value={currentChapter}
        onChange={(e) => {
          router.push(`/read/${bookId}/${e.target.value}`)
        }}
        className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-sm focus:border-indigo-500 focus:outline-none"
      >
        {chapters.map((ch) => (
          <option key={ch.number} value={ch.number}>
            Ch. {ch.number} — {ch.title || `Chapter ${ch.number}`}
          </option>
        ))}
      </select>

      {hasNext && nextChapter ? (
        <Button variant="outline" size="sm" asChild>
          <Link href={`/read/${bookId}/${nextChapter.number}`}>
            Ch. {nextChapter.number}
            <ChevronRight className="h-4 w-4 ml-1" />
          </Link>
        </Button>
      ) : (
        <div />
      )}
    </div>
  )
}
