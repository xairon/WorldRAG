import { create } from "zustand"

interface UIState {
  // Existing
  mobileSidebarOpen: boolean
  setMobileSidebarOpen: (open: boolean) => void
  commandOpen: boolean
  toggleCommandOpen: () => void

  // New
  sidebarExpanded: boolean
  setSidebarExpanded: (expanded: boolean) => void

  /** Which books have their accordion expanded in sidebar */
  expandedBooks: Record<string, boolean>
  toggleBookExpanded: (bookId: string) => void
}

export const useUIStore = create<UIState>((set) => ({
  // Existing
  mobileSidebarOpen: false,
  setMobileSidebarOpen: (open) => set({ mobileSidebarOpen: open }),
  commandOpen: false,
  toggleCommandOpen: () => set((s) => ({ commandOpen: !s.commandOpen })),

  // New
  sidebarExpanded: true,
  setSidebarExpanded: (expanded) => set({ sidebarExpanded: expanded }),

  expandedBooks: {},
  toggleBookExpanded: (bookId) =>
    set((state) => ({
      expandedBooks: {
        ...state.expandedBooks,
        [bookId]: !state.expandedBooks[bookId],
      },
    })),
}))
