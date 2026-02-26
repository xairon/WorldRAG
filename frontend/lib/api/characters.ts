import { apiFetch } from "./client"

// --- Nested snapshot types ---

export interface StatEntry {
  name: string
  value: number
  last_changed_chapter: number
}

export interface SkillSnapshot {
  name: string
  rank: string
  skill_type: string
  description: string
  acquired_chapter: number | null
}

export interface ClassSnapshot {
  name: string
  tier: number | null
  description: string
  acquired_chapter: number | null
  is_active: boolean
}

export interface TitleSnapshot {
  name: string
  description: string
  effects: string[]
  acquired_chapter: number | null
}

export interface ItemSnapshot {
  name: string
  item_type: string
  rarity: string
  description: string
  acquired_chapter: number | null
  grants: string[]
}

export interface LevelSnapshot {
  level: number | null
  realm: string
  since_chapter: number | null
}

export interface StateChangeRecord {
  chapter: number
  category: string
  name: string
  action: string
  value_delta: number | null
  value_after: number | null
  detail: string
}

// --- Top-level response types ---

export interface CharacterStateSnapshot {
  character_name: string
  canonical_name: string
  book_id: string
  as_of_chapter: number
  total_chapters_in_book: number
  role: string
  species: string
  description: string
  aliases: string[]
  level: LevelSnapshot
  stats: StatEntry[]
  skills: SkillSnapshot[]
  classes: ClassSnapshot[]
  titles: TitleSnapshot[]
  items: ItemSnapshot[]
  chapter_changes: StateChangeRecord[]
  total_changes_to_date: number
}

export interface ProgressionMilestone {
  chapter: number
  category: string
  name: string
  action: string
  value_delta: number | null
  value_after: number | null
  detail: string
}

export interface ProgressionTimeline {
  character_name: string
  book_id: string
  milestones: ProgressionMilestone[]
  total: number
  offset: number
  limit: number
}

export interface StatDiff {
  name: string
  value_at_from: number
  value_at_to: number
  delta: number
}

export interface CategoryDiff {
  gained: string[]
  lost: string[]
}

export interface CharacterComparison {
  character_name: string
  book_id: string
  from_chapter: number
  to_chapter: number
  level_from: number | null
  level_to: number | null
  stat_diffs: StatDiff[]
  skills: CategoryDiff
  classes: CategoryDiff
  titles: CategoryDiff
  items: CategoryDiff
  total_changes: number
}

export interface CharacterSummary {
  name: string
  canonical_name: string
  role: string
  species: string
  level: number | null
  realm: string
  active_class: string | null
  top_skills: string[]
  description: string
}

// --- API functions ---

export function getCharacterStateAt(
  name: string,
  chapter: number,
  bookId: string,
): Promise<CharacterStateSnapshot> {
  const params = new URLSearchParams({ book_id: bookId })
  return apiFetch(`/characters/${encodeURIComponent(name)}/at/${chapter}?${params}`)
}

export function getCharacterProgression(
  name: string,
  bookId: string,
  options?: { category?: string; offset?: number; limit?: number },
): Promise<ProgressionTimeline> {
  const params = new URLSearchParams({ book_id: bookId })
  if (options?.category) params.set("category", options.category)
  if (options?.offset !== undefined) params.set("offset", String(options.offset))
  if (options?.limit !== undefined) params.set("limit", String(options.limit))
  return apiFetch(`/characters/${encodeURIComponent(name)}/progression?${params}`)
}

export function compareCharacterState(
  name: string,
  bookId: string,
  from: number,
  to: number,
): Promise<CharacterComparison> {
  const params = new URLSearchParams({
    book_id: bookId,
    from: String(from),
    to: String(to),
  })
  return apiFetch(`/characters/${encodeURIComponent(name)}/compare?${params}`)
}

export function getCharacterSummary(
  name: string,
  options?: { bookId?: string; chapter?: number },
): Promise<CharacterSummary> {
  const params = new URLSearchParams()
  if (options?.bookId) params.set("book_id", options.bookId)
  if (options?.chapter !== undefined) params.set("chapter", String(options.chapter))
  const qs = params.toString()
  return apiFetch(`/characters/${encodeURIComponent(name)}/summary${qs ? `?${qs}` : ""}`)
}
