import { create } from "zustand"
import type { BookInfo, ChapterInfo } from "@/lib/api/types"

interface BookState {
  selectedBookId: string | null
  book: BookInfo | null
  chapters: ChapterInfo[]
  spoilerChapter: number | null // null = no spoiler guard

  setSelectedBookId: (id: string | null) => void
  setBook: (book: BookInfo | null) => void
  setChapters: (chapters: ChapterInfo[]) => void
  setSpoilerChapter: (chapter: number | null) => void
  reset: () => void
}

export const useBookStore = create<BookState>((set) => ({
  selectedBookId: null,
  book: null,
  chapters: [],
  spoilerChapter: null,

  setSelectedBookId: (id) => set({ selectedBookId: id }),
  setBook: (book) => set({ book }),
  setChapters: (chapters) => set({ chapters }),
  setSpoilerChapter: (chapter) => set({ spoilerChapter: chapter }),
  reset: () => set({ selectedBookId: null, book: null, chapters: [], spoilerChapter: null }),
}))
