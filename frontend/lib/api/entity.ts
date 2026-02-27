import { apiFetch } from "./client"

export interface EntityConnection {
  target_name: string
  target_label: string
  target_id: string
  direction: "incoming" | "outgoing"
  properties: Record<string, unknown>
}

export interface EntityAppearance {
  chapter: number
  title: string
}

export interface EntityWiki {
  id: string
  labels: string[]
  properties: Record<string, unknown>
  connections: Record<string, EntityConnection[]>
  appearances: EntityAppearance[]
}

export function getEntityWiki(
  entityType: string,
  entityName: string,
  bookId?: string,
): Promise<EntityWiki> {
  const params = new URLSearchParams()
  if (bookId) params.set("book_id", bookId)
  const qs = params.toString()
  return apiFetch(`/graph/wiki/${encodeURIComponent(entityType)}/${encodeURIComponent(entityName)}${qs ? `?${qs}` : ""}`)
}
