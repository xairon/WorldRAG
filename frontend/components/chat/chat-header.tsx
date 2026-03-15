"use client"

import { useChatStore } from "@/stores/chat-store"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"

interface Book {
  id: string
  title: string
  totalChapters: number
}

interface ChatHeaderProps {
  books: Book[]
}

export function ChatHeader({ books }: ChatHeaderProps) {
  const selectedBookId = useChatStore((s) => s.selectedBookId)
  const spoilerMaxChapter = useChatStore((s) => s.spoilerMaxChapter)
  const setSelectedBookId = useChatStore((s) => s.setSelectedBookId)
  const setSpoilerMaxChapter = useChatStore((s) => s.setSpoilerMaxChapter)

  const selectedBook = books.find((b) => b.id === selectedBookId)
  const totalChapters = selectedBook?.totalChapters ?? 0
  const spoilerLimitActive =
    spoilerMaxChapter !== null && spoilerMaxChapter < totalChapters

  return (
    <div className="flex items-center gap-3 border-b px-4 py-2">
      <Select
        value={selectedBookId ?? ""}
        onValueChange={(value) =>
          setSelectedBookId(value === "" ? null : value)
        }
      >
        <SelectTrigger className="w-[220px]">
          <SelectValue placeholder="Select a book" />
        </SelectTrigger>
        <SelectContent>
          {books.map((book) => (
            <SelectItem key={book.id} value={book.id}>
              {book.title}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {selectedBook && totalChapters > 0 && (
        <>
          <Select
            value={spoilerMaxChapter === null ? "all" : String(spoilerMaxChapter)}
            onValueChange={(value) =>
              setSpoilerMaxChapter(value === "all" ? null : Number(value))
            }
          >
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder="Spoiler limit" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All chapters</SelectItem>
              {Array.from({ length: totalChapters }, (_, i) => i + 1).map(
                (ch) => (
                  <SelectItem key={ch} value={String(ch)}>
                    Ch. 1–{ch}
                  </SelectItem>
                ),
              )}
            </SelectContent>
          </Select>

          {spoilerLimitActive && (
            <Badge
              variant="outline"
              className="border-amber-500 bg-amber-500/10 text-amber-600 dark:text-amber-400"
            >
              Spoiler limit active
            </Badge>
          )}
        </>
      )}
    </div>
  )
}
