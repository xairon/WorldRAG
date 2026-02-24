/**
 * WorldRAG API client.
 *
 * All fetch calls to the FastAPI backend go through this module.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: HeadersInit = { ...(init?.headers as Record<string, string>) };
  // Only set JSON content type when body is not FormData
  if (!(init?.body instanceof FormData)) {
    (headers as Record<string, string>)["Content-Type"] = "application/json";
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `API error ${res.status}`);
  }
  return res.json();
}

// ── Health ──────────────────────────────────────────────────────────────────

export interface HealthStatus {
  status: string;
  services: Record<string, string>;
}

export function getHealth(): Promise<HealthStatus> {
  return apiFetch("/health");
}

// ── Books ───────────────────────────────────────────────────────────────────

export interface BookInfo {
  id: string;
  title: string;
  series_name: string | null;
  order_in_series: number | null;
  author: string | null;
  genre: string;
  total_chapters: number;
  status: string;
  chapters_processed: number;
}

export interface ChapterInfo {
  number: number;
  title: string;
  word_count: number;
  chunk_count: number;
  entity_count: number;
  status: string;
  regex_matches: number;
}

export interface BookDetail {
  book: BookInfo;
  chapters: ChapterInfo[];
}

export interface IngestionResult {
  book_id: string;
  title: string;
  chapters_found: number;
  chunks_created: number;
  regex_matches_total: number;
  status: string;
}

export interface ExtractionResult {
  book_id: string;
  chapters_processed: number;
  chapters_failed: number;
  failed_chapters: number[];
  total_entities: number;
  status: string;
}

export function listBooks(): Promise<BookInfo[]> {
  return apiFetch("/books");
}

export function getBook(id: string): Promise<BookDetail> {
  return apiFetch(`/books/${id}`);
}

export function getBookStats(id: string): Promise<Record<string, unknown>> {
  return apiFetch(`/books/${id}/stats`);
}

export async function uploadBook(form: FormData): Promise<IngestionResult> {
  const res = await fetch(`${API_BASE}/books`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Upload failed: ${res.status}`);
  }
  return res.json();
}

export function extractBook(id: string): Promise<ExtractionResult> {
  return apiFetch(`/books/${id}/extract`, { method: "POST" });
}

export function deleteBook(id: string): Promise<{ deleted: boolean }> {
  return apiFetch(`/books/${id}`, { method: "DELETE" });
}

// ── Graph ───────────────────────────────────────────────────────────────────

export interface GraphStats {
  nodes: Record<string, number>;
  relationships: Record<string, number>;
  total_nodes: number;
  total_relationships: number;
}

export interface GraphNode {
  id: string;
  labels: string[];
  name: string;
  description?: string;
}

export interface GraphEdge {
  id: string;
  type: string;
  source: string;
  target: string;
  properties?: Record<string, unknown>;
}

export interface SubgraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface CharacterProfile {
  id: string;
  properties: Record<string, unknown>;
  skills: Array<{ name: string; rank: string; type: string; description: string; since_chapter: number }>;
  classes: Array<{ name: string; tier: number; description: string; since_chapter: number }>;
  titles: Array<{ name: string; description: string; acquired_chapter: number }>;
  relationships: Array<{ name: string; rel_type: string; subtype: string; context: string; since_chapter: number }>;
  events: Array<{ name: string; description: string; type: string; significance: string; chapter: number }>;
}

export interface TimelineEvent {
  name: string;
  description: string;
  type: string;
  significance: string;
  chapter: number;
  participants: string[];
  locations: string[];
}

export function getGraphStats(bookId?: string): Promise<GraphStats> {
  const q = bookId ? `?book_id=${bookId}` : "";
  return apiFetch(`/graph/stats${q}`);
}

export function searchEntities(query: string, label?: string, bookId?: string): Promise<GraphNode[]> {
  const params = new URLSearchParams({ q: query });
  if (label) params.set("label", label);
  if (bookId) params.set("book_id", bookId);
  return apiFetch(`/graph/search?${params}`);
}

export function getSubgraph(bookId: string, label?: string, chapter?: number): Promise<SubgraphData> {
  const params = new URLSearchParams();
  if (label) params.set("label", label);
  if (chapter) params.set("chapter", String(chapter));
  const q = params.toString() ? `?${params}` : "";
  return apiFetch(`/graph/subgraph/${bookId}${q}`);
}

export function getCharacterProfile(name: string, bookId?: string): Promise<CharacterProfile> {
  const q = bookId ? `?book_id=${bookId}` : "";
  return apiFetch(`/graph/characters/${encodeURIComponent(name)}${q}`);
}

export function getTimeline(bookId: string, significance?: string): Promise<TimelineEvent[]> {
  const q = significance ? `?significance=${significance}` : "";
  return apiFetch(`/graph/timeline/${bookId}${q}`);
}
