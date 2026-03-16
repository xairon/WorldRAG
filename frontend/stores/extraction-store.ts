import { create } from "zustand"

export interface FeedMessage {
  time: string
  chapter: number
  type: string
  name: string
}

export interface ErrorDetail {
  type: string
  provider: string
  message: string
}

interface ExtractionState {
  status: "idle" | "running" | "done" | "error" | "error_quota"
  chaptersTotal: number
  chaptersDone: number
  entitiesFound: number
  feedMessages: FeedMessage[]
  errorDetail: ErrorDetail | null
  addFeedMessage: (msg: FeedMessage) => void
  setProgress: (data: { chaptersTotal?: number; chaptersDone?: number; entitiesFound?: number }) => void
  setStatus: (status: ExtractionState["status"]) => void
  setErrorDetail: (detail: ErrorDetail | null) => void
  reset: () => void
}

export const useExtractionStore = create<ExtractionState>((set) => ({
  status: "idle",
  chaptersTotal: 0,
  chaptersDone: 0,
  entitiesFound: 0,
  feedMessages: [],
  errorDetail: null,
  addFeedMessage: (msg) =>
    set((state) => ({ feedMessages: [...state.feedMessages.slice(-500), msg] })),
  setProgress: (data) =>
    set((state) => ({
      chaptersTotal: data.chaptersTotal ?? state.chaptersTotal,
      chaptersDone: data.chaptersDone ?? state.chaptersDone,
      entitiesFound: data.entitiesFound ?? state.entitiesFound,
    })),
  setStatus: (status) => set({ status }),
  setErrorDetail: (detail) => set({ errorDetail: detail }),
  reset: () => set({
    status: "idle",
    chaptersTotal: 0,
    chaptersDone: 0,
    entitiesFound: 0,
    feedMessages: [],
    errorDetail: null,
  }),
}))
