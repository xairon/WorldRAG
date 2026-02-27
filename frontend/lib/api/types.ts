// ── Shared API types ────────────────────────────────────────────────────────

export interface HealthStatus {
  status: string
  services: Record<string, string>
}

// ── Books ───────────────────────────────────────────────────────────────────

export interface BookInfo {
  id: string
  title: string
  series_name: string | null
  order_in_series: number | null
  author: string | null
  genre: string
  total_chapters: number
  status: string
  chapters_processed: number
  total_cost_usd: number
}

export interface ChapterInfo {
  number: number
  title: string
  word_count: number
  chunk_count: number
  entity_count: number
  status: string
  regex_matches: number
}

export interface BookDetail {
  book: BookInfo
  chapters: ChapterInfo[]
}

export interface IngestionResult {
  book_id: string
  title: string
  chapters_found: number
  chunks_created: number
  regex_matches_total: number
  status: string
}

export interface ExtractionResult {
  book_id: string
  job_id: string
  status: string
  message: string
}

// ── Graph ───────────────────────────────────────────────────────────────────

export interface GraphStats {
  nodes: Record<string, number>
  relationships: Record<string, number>
  total_nodes: number
  total_relationships: number
}

export interface GraphNode {
  id: string
  labels: string[]
  name: string
  description?: string
  canonical_name?: string
  score?: number
}

export interface GraphEdge {
  id: string
  type: string
  source: string
  target: string
  properties?: Record<string, unknown>
}

export interface SubgraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface CharacterProfile {
  id: string
  properties: Record<string, unknown>
  skills: Array<{ name: string; rank: string; type: string; description: string; since_chapter: number }>
  classes: Array<{ name: string; tier: number; description: string; since_chapter: number }>
  titles: Array<{ name: string; description: string; acquired_chapter: number }>
  relationships: Array<{ name: string; rel_type: string; subtype: string; context: string; since_chapter: number }>
  events: Array<{ name: string; description: string; type: string; significance: string; chapter: number }>
}

export interface TimelineEvent {
  name: string
  description: string
  type: string
  significance: string
  chapter: number
  participants: string[]
  locations: string[]
}

// ── Chat ────────────────────────────────────────────────────────────────────

export interface SourceChunk {
  text: string
  chapter_number: number
  chapter_title: string
  position: number
  relevance_score: number
}

export interface RelatedEntity {
  name: string
  label: string
  description: string
}

export interface ChatResponse {
  answer: string
  sources: SourceChunk[]
  related_entities: RelatedEntity[]
  chunks_retrieved: number
  chunks_after_rerank: number
}
