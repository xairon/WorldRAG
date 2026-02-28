import { apiFetch } from "./client"
import type { GraphStats, GraphNode, SubgraphData, CharacterProfile, TimelineEvent } from "./types"

export function getGraphStats(bookId?: string): Promise<GraphStats> {
  const q = bookId ? `?book_id=${bookId}` : ""
  return apiFetch(`/graph/stats${q}`)
}

export function searchEntities(query: string, label?: string, bookId?: string): Promise<GraphNode[]> {
  const params = new URLSearchParams({ q: query })
  if (label) params.set("label", label)
  if (bookId) params.set("book_id", bookId)
  return apiFetch(`/graph/search?${params}`)
}

export function getSubgraph(bookId: string, label?: string, chapter?: number): Promise<SubgraphData> {
  const params = new URLSearchParams()
  if (label) params.set("label", label)
  if (chapter) params.set("chapter", String(chapter))
  const q = params.toString() ? `?${params}` : ""
  return apiFetch(`/graph/subgraph/${bookId}${q}`)
}

export function getCharacterProfile(name: string, bookId?: string): Promise<CharacterProfile> {
  const q = bookId ? `?book_id=${bookId}` : ""
  return apiFetch(`/graph/characters/${encodeURIComponent(name)}${q}`)
}

export function getTimeline(bookId: string, significance?: string, character?: string): Promise<TimelineEvent[]> {
  const params = new URLSearchParams()
  if (significance) params.set("significance", significance)
  if (character) params.set("character", character)
  const q = params.toString() ? `?${params}` : ""
  return apiFetch(`/graph/timeline/${bookId}${q}`)
}

export function listEntities(
  bookId: string,
  label: string,
  limit = 50,
  offset = 0,
): Promise<{ entities: GraphNode[]; total: number; limit: number; offset: number }> {
  const params = new URLSearchParams({
    book_id: bookId,
    label,
    limit: String(limit),
    offset: String(offset),
  })
  return apiFetch(`/graph/entities?${params}`)
}
