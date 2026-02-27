"use client"

import { useState, useCallback, useRef } from "react"
import { chatStream } from "@/lib/api/chat"
import type { ChatStreamSourcesEvent } from "@/lib/api/chat"
import type { SourceChunk, RelatedEntity } from "@/lib/api/types"

export interface ChatMessage {
  id: string
  role: "user" | "assistant" | "system"
  content: string
  timestamp: Date
  sources?: SourceChunk[]
  relatedEntities?: RelatedEntity[]
  chunksRetrieved?: number
  chunksAfterRerank?: number
  isStreaming?: boolean
}

interface UseChatStreamReturn {
  messages: ChatMessage[]
  isStreaming: boolean
  send: (query: string, bookId: string, maxChapter?: number) => void
  stop: () => void
  clearMessages: () => void
}

const WELCOME_MESSAGE: ChatMessage = {
  id: "welcome",
  role: "system",
  content: "Welcome to WorldRAG Chat! Select a book and ask questions about the story, characters, events, or lore.",
  timestamp: new Date(),
}

export function useChatStream(): UseChatStreamReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE])
  const [isStreaming, setIsStreaming] = useState(false)
  const isStreamingRef = useRef(false)
  const controllerRef = useRef<AbortController | null>(null)
  const assistantIdRef = useRef<string>("")

  const stop = useCallback(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
    isStreamingRef.current = false
    setIsStreaming(false)
    // Mark the current assistant message as not streaming
    setMessages((prev) =>
      prev.map((m) => (m.id === assistantIdRef.current ? { ...m, isStreaming: false } : m)),
    )
  }, [])

  const send = useCallback(
    (query: string, bookId: string, maxChapter?: number) => {
      if (isStreamingRef.current) return

      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: query,
        timestamp: new Date(),
      }

      const assistantId = crypto.randomUUID()
      assistantIdRef.current = assistantId
      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: new Date(),
        isStreaming: true,
      }

      setMessages((prev) => [...prev, userMsg, assistantMsg])
      isStreamingRef.current = true
      setIsStreaming(true)

      const controller = chatStream(query, bookId, {
        onSources(data: ChatStreamSourcesEvent) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    sources: data.sources,
                    relatedEntities: data.related_entities,
                    chunksRetrieved: data.chunks_retrieved,
                    chunksAfterRerank: data.chunks_after_rerank,
                  }
                : m,
            ),
          )
        },
        onToken(token: string) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + token } : m,
            ),
          )
        },
        onDone() {
          isStreamingRef.current = false
          setIsStreaming(false)
          controllerRef.current = null
          setMessages((prev) =>
            prev.map((m) => (m.id === assistantId ? { ...m, isStreaming: false } : m)),
          )
        },
        onError(message: string) {
          isStreamingRef.current = false
          setIsStreaming(false)
          controllerRef.current = null
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content || `Error: ${message}`, isStreaming: false }
                : m,
            ),
          )
        },
      }, maxChapter)

      controllerRef.current = controller
    },
    [],
  )

  const clearMessages = useCallback(() => {
    stop()
    setMessages([WELCOME_MESSAGE])
  }, [stop])

  return { messages, isStreaming, send, stop, clearMessages }
}
