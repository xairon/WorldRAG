import { create } from "zustand"

export interface FeedMessage {
  time: string
  chapter: number
  type: string
  name: string
}

interface ExtractionState {
  status: "idle" | "running" | "done" | "error"
  chaptersTotal: number
  chaptersDone: number
  entitiesFound: number
  feedMessages: FeedMessage[]
  addFeedMessage: (msg: FeedMessage) => void
  setProgress: (data: { chaptersTotal?: number; chaptersDone?: number; entitiesFound?: number }) => void
  setStatus: (status: ExtractionState["status"]) => void
  reset: () => void
}

export const useExtractionStore = create<ExtractionState>((set) => ({
  status: "idle",
  chaptersTotal: 0,
  chaptersDone: 0,
  entitiesFound: 0,
  feedMessages: [],
  addFeedMessage: (msg) =>
    set((state) => ({ feedMessages: [...state.feedMessages.slice(-500), msg] })),
  setProgress: (data) =>
    set((state) => ({
      chaptersTotal: data.chaptersTotal ?? state.chaptersTotal,
      chaptersDone: data.chaptersDone ?? state.chaptersDone,
      entitiesFound: data.entitiesFound ?? state.entitiesFound,
    })),
  setStatus: (status) => set({ status }),
  reset: () => set({ status: "idle", chaptersTotal: 0, chaptersDone: 0, entitiesFound: 0, feedMessages: [] }),
}))
