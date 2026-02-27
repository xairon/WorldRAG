import { apiFetch, API_BASE } from "./client"
import type { ChatResponse, SourceChunk, RelatedEntity } from "./types"

export interface ChatQueryOptions {
  maxChapter?: number
  topK?: number
  rerankTopN?: number
  minRelevance?: number
  includeSources?: boolean
}

export function chatQuery(
  query: string,
  bookId: string,
  options?: ChatQueryOptions,
): Promise<ChatResponse> {
  return apiFetch("/chat/query", {
    method: "POST",
    body: JSON.stringify({
      query,
      book_id: bookId,
      ...(options?.maxChapter != null && { max_chapter: options.maxChapter }),
      ...(options?.topK != null && { top_k: options.topK }),
      ...(options?.rerankTopN != null && { rerank_top_n: options.rerankTopN }),
      ...(options?.minRelevance != null && { min_relevance: options.minRelevance }),
      ...(options?.includeSources != null && { include_sources: options.includeSources }),
    }),
  })
}

/** SSE event types from the /chat/stream endpoint */
export interface ChatStreamSourcesEvent {
  sources: SourceChunk[]
  related_entities: RelatedEntity[]
  chunks_retrieved: number
  chunks_after_rerank: number
}

export interface ChatStreamCallbacks {
  onSources: (data: ChatStreamSourcesEvent) => void
  onToken: (token: string) => void
  onDone: () => void
  onError: (message: string) => void
}

/**
 * Connect to the SSE chat stream endpoint.
 * Returns an AbortController to cancel the stream.
 */
export function chatStream(
  query: string,
  bookId: string,
  callbacks: ChatStreamCallbacks,
  maxChapter?: number,
): AbortController {
  const controller = new AbortController()

  const params = new URLSearchParams({
    q: query,
    book_id: bookId,
  })
  if (maxChapter != null) {
    params.set("max_chapter", String(maxChapter))
  }

  const url = `${API_BASE}/chat/stream?${params.toString()}`

  ;(async () => {
    try {
      const res = await fetch(url, { signal: controller.signal })
      if (!res.ok) {
        callbacks.onError(`API error ${res.status}`)
        return
      }

      const reader = res.body?.getReader()
      if (!reader) {
        callbacks.onError("No response body")
        return
      }

      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split("\n")
        buffer = lines.pop() ?? ""

        let currentEvent = ""
        for (const line of lines) {
          if (line.startsWith("event:")) {
            currentEvent = line.slice(6).trim()
          } else if (line.startsWith("data:")) {
            const rawData = line.slice(5).trim()
            if (!rawData) continue

            try {
              const data = JSON.parse(rawData)
              switch (currentEvent) {
                case "sources":
                  callbacks.onSources(data as ChatStreamSourcesEvent)
                  break
                case "token":
                  callbacks.onToken(data.token)
                  break
                case "done":
                  callbacks.onDone()
                  break
                case "error":
                  callbacks.onError(data.message)
                  break
              }
            } catch {
              // non-JSON data line, skip
            }
            currentEvent = ""
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        callbacks.onError((err as Error).message ?? "Stream failed")
      }
    }
  })()

  return controller
}
