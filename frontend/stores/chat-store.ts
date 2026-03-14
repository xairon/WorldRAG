import { create } from "zustand"
import { persist } from "zustand/middleware"

export interface ChatThread {
  id: string
  bookId: string
  title: string
  createdAt: string
  updatedAt: string
}

interface ChatState {
  threadId: string | null
  threads: ChatThread[]

  setThreadId: (id: string | null) => void
  addThread: (thread: ChatThread) => void
  removeThread: (id: string) => void
  updateThreadTitle: (id: string, title: string) => void
  clearThreads: () => void
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      threadId: null,
      threads: [],

      setThreadId: (id) => set({ threadId: id }),
      addThread: (thread) =>
        set((s) => ({ threads: [thread, ...s.threads].slice(0, 50) })),
      removeThread: (id) =>
        set((s) => ({
          threads: s.threads.filter((t) => t.id !== id),
          threadId: s.threadId === id ? null : s.threadId,
        })),
      updateThreadTitle: (id, title) =>
        set((s) => ({
          threads: s.threads.map((t) =>
            t.id === id ? { ...t, title, updatedAt: new Date().toISOString() } : t,
          ),
        })),
      clearThreads: () => set({ threads: [], threadId: null }),
    }),
    { name: "worldrag-chat" },
  ),
)
