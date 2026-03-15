import { create } from "zustand"

interface ReaderState {
  currentBookId: string | null
  currentChapter: number
  totalChapters: number
  setBook: (bookId: string, totalChapters: number) => void
  setChapter: (chapter: number) => void
}

export const useReaderStore = create<ReaderState>((set) => ({
  currentBookId: null,
  currentChapter: 1,
  totalChapters: 0,
  setBook: (bookId, totalChapters) => set({ currentBookId: bookId, totalChapters }),
  setChapter: (chapter) => set({ currentChapter: chapter }),
}))
