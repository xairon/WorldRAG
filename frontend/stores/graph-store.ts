import { create } from "zustand"
import type { GraphNode, SubgraphData } from "@/lib/api/types"

interface GraphFilters {
  labels: string[]
  chapterRange: [number, number] | null
}

interface GraphState {
  graphData: SubgraphData
  filters: GraphFilters
  selectedNode: GraphNode | null
  layout: "forceatlas2" | "circular"
  loading: boolean

  setGraphData: (data: SubgraphData) => void
  setFilters: (filters: Partial<GraphFilters>) => void
  toggleLabel: (label: string) => void
  setSelectedNode: (node: GraphNode | null) => void
  setLayout: (layout: "forceatlas2" | "circular") => void
  setLoading: (loading: boolean) => void
  reset: () => void
}

const defaultFilters: GraphFilters = {
  labels: [],
  chapterRange: null,
}

export const useGraphStore = create<GraphState>((set) => ({
  graphData: { nodes: [], edges: [] },
  filters: defaultFilters,
  selectedNode: null,
  layout: "forceatlas2",
  loading: false,

  setGraphData: (data) => set({ graphData: data }),
  setFilters: (partial) => set((s) => ({ filters: { ...s.filters, ...partial } })),
  toggleLabel: (label) =>
    set((s) => ({
      filters: {
        ...s.filters,
        labels: s.filters.labels.includes(label)
          ? s.filters.labels.filter((l) => l !== label)
          : [...s.filters.labels, label],
      },
    })),
  setSelectedNode: (node) => set({ selectedNode: node }),
  setLayout: (layout) => set({ layout }),
  setLoading: (loading) => set({ loading }),
  reset: () => set({ graphData: { nodes: [], edges: [] }, filters: defaultFilters, selectedNode: null }),
}))
