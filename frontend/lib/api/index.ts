// Re-export everything for backwards compatibility and convenience
export type {
  HealthStatus,
  BookInfo,
  ChapterInfo,
  BookDetail,
  IngestionResult,
  ExtractionResult,
  GraphStats,
  GraphNode,
  GraphEdge,
  SubgraphData,
  CharacterProfile,
  TimelineEvent,
  SourceChunk,
  RelatedEntity,
  ChatResponse,
} from "./types"

export { apiFetch } from "./client"
export { listBooks, getBook, getBookStats, uploadBook, extractBook, deleteBook, getBookJobs } from "./books"
export type { BookJobs, BookJobStatus } from "./books"
export { getGraphStats, searchEntities, getSubgraph, getCharacterProfile, getTimeline } from "./graph"
export { chatQuery, chatStream } from "./chat"
export type { ChatStreamSourcesEvent, ChatStreamCallbacks, ChatQueryOptions } from "./chat"
export { getChapterText, getChapterEntities, getChapterParagraphs } from "./reader"
export type { ChapterText, EntityAnnotation, ChapterEntities, ChapterParagraphs, ParagraphData } from "./reader"
export { getEntityWiki } from "./entity"
export type { EntityWiki, EntityConnection, EntityAppearance } from "./entity"
export { getPipelineConfig } from "./pipeline"
export type { PipelineConfig, PromptInfo, RegexPatternInfo, OntologyNodeType, OntologyRelType } from "./pipeline"
export { getCharacterStateAt, getCharacterProgression, compareCharacterState, getCharacterSummary } from "./characters"
export type {
  CharacterStateSnapshot, CharacterSummary, CharacterComparison, ProgressionTimeline,
  StatEntry, SkillSnapshot, ClassSnapshot, TitleSnapshot, ItemSnapshot,
  LevelSnapshot, StateChangeRecord, ProgressionMilestone, StatDiff, CategoryDiff,
} from "./characters"

// Health
import { apiFetch } from "./client"
import type { HealthStatus } from "./types"

export function getHealth(): Promise<HealthStatus> {
  return apiFetch("/health")
}
