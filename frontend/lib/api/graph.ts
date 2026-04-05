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

// ── Ontology ──────────────────────────────────────────────────────────────

export interface OntologyEntityType {
  label: string
  count: number
  layer: "core" | "genre" | "induced"
  golem_alignment?: string
  description?: string
  golem_category?: string
  sample_entities: string[]
  avg_confidence: number
}

export interface OntologyRelationType {
  type: string
  count: number
  temporal: boolean
  source_types?: string[]
  target_types?: string[]
}

export interface OntologySchemaEdge {
  source: string
  relation: string
  target: string
  count: number
}

export interface OntologyData {
  entity_types: OntologyEntityType[]
  relation_types: OntologyRelationType[]
  schema_edges: OntologySchemaEdge[]
  stats: {
    total_entities: number
    total_relations: number
    entity_type_count: number
    relation_type_count: number
    avg_relations_per_entity: number
  }
  induced_types: string[]
}

export function getOntology(bookId: string): Promise<OntologyData> {
  return apiFetch(`/graph/ontology/${bookId}`)
}

// ── Entities ──────────────────────────────────────────────────────────────

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
