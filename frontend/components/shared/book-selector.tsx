"use client"

import { useEffect, useState } from "react"
import { BookOpen, ChevronDown } from "lucide-react"
import { useBookStore } from "@/stores/book-store"
import { listBooks, getBook } from "@/lib/api/books"
import type { BookInfo } from "@/lib/api/types"
import { cn, statusColor } from "@/lib/utils"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu"

export function BookSelector() {
  const { selectedBookId, setSelectedBookId, setBook, setChapters, book } = useBookStore()
  const [books, setBooks] = useState<BookInfo[]>([])

  useEffect(() => {
    listBooks().then(setBooks).catch(() => {})
  }, [])

  // Load book detail when selection changes
  useEffect(() => {
    if (!selectedBookId) {
      setBook(null)
      setChapters([])
      return
    }
    getBook(selectedBookId).then((detail) => {
      setBook(detail.book)
      setChapters(detail.chapters)
    }).catch(() => {})
  }, [selectedBookId, setBook, setChapters])

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center gap-2 rounded-lg glass px-3 py-1.5 text-sm glass-hover transition-colors max-w-[220px]">
          <BookOpen className="h-4 w-4 text-primary shrink-0" />
          <span className="truncate text-foreground">
            {book ? book.title : "Select book..."}
          </span>
          <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        <DropdownMenuItem
          onClick={() => setSelectedBookId(null)}
          className={cn(!selectedBookId && "bg-accent")}
        >
          <span className="text-muted-foreground">No book selected</span>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {books.map((b) => (
          <DropdownMenuItem
            key={b.id}
            onClick={() => setSelectedBookId(b.id)}
            className={cn(selectedBookId === b.id && "bg-accent")}
          >
            <div className="flex items-center justify-between w-full gap-2">
              <span className="truncate">{b.title}</span>
              <span className={cn(
                "text-[9px] font-medium px-1.5 py-0.5 rounded-full border shrink-0",
                statusColor(b.status),
              )}>
                {b.status}
              </span>
            </div>
          </DropdownMenuItem>
        ))}
        {books.length === 0 && (
          <DropdownMenuItem disabled>
            <span className="text-muted-foreground">No books uploaded</span>
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
