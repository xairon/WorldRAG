// Re-export public API modules
export type {
  HealthStatus,
  GraphNode,
  GraphEdge,
  SubgraphData,
  SourceChunk,
  RelatedEntity,
  ChatResponse,
} from "./types"

export { apiFetch } from "./client"
export { getGraphStats, searchEntities, getSubgraph, listEntities } from "./graph"
export { chatQuery, chatStream } from "./chat"
export type { ChatStreamSourcesEvent, ChatStreamCallbacks, ChatQueryOptions } from "./chat"

// Health
import { apiFetch } from "./client"
import type { HealthStatus } from "./types"

export function getHealth(): Promise<HealthStatus> {
  return apiFetch("/health")
}
