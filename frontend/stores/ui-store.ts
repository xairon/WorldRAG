import { create } from "zustand"

interface UIState {
  mobileSidebarOpen: boolean
  commandOpen: boolean

  toggleSidebar: () => void
  setMobileSidebarOpen: (collapsed: boolean) => void
  setCommandOpen: (open: boolean) => void
  toggleCommandOpen: () => void
}

export const useUIStore = create<UIState>((set) => ({
  mobileSidebarOpen: false,
  commandOpen: false,

  toggleSidebar: () => set((s) => ({ mobileSidebarOpen: !s.mobileSidebarOpen })),
  setMobileSidebarOpen: (collapsed) => set({ mobileSidebarOpen: collapsed }),
  setCommandOpen: (open) => set({ commandOpen: open }),
  toggleCommandOpen: () => set((s) => ({ commandOpen: !s.commandOpen })),
}))
