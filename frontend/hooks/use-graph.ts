"use client"

import { useQuery } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api/client"
import type { GraphNode, SubgraphData } from "@/lib/api/types"

export function useSubgraph(
  bookId: string | null,
  filters?: { labels?: string[]; chapter?: number },
) {
  const labels = filters?.labels?.join(",") ?? ""
  const chapter = filters?.chapter

  return useQuery({
    queryKey: ["graph", "subgraph", bookId, labels, chapter],
    queryFn: () => {
      const params = new URLSearchParams()
      if (labels) params.set("label", labels)
      if (chapter) params.set("chapter", String(chapter))
      const q = params.toString() ? `?${params}` : ""
      return apiFetch<SubgraphData>(`/graph/subgraph/${bookId}${q}`)
    },
    enabled: !!bookId,
    staleTime: 5 * 60_000,
  })
}

export function useNeighbors(entityId: string | null) {
  return useQuery({
    queryKey: ["graph", "neighbors", entityId],
    queryFn: () =>
      apiFetch<SubgraphData>(
        `/graph/neighbors/${entityId}?depth=1&limit=50`,
      ),
    enabled: !!entityId,
    staleTime: 5 * 60_000,
  })
}

export function useGraphSearch(bookId: string | null, query: string) {
  return useQuery({
    queryKey: ["graph", "search", bookId, query],
    queryFn: () => {
      const params = new URLSearchParams({ q: query })
      if (bookId) params.set("book_id", bookId)
      params.set("limit", "10")
      return apiFetch<GraphNode[]>(`/graph/search?${params}`)
    },
    enabled: !!bookId && query.length >= 2,
    staleTime: 30_000,
  })
}
