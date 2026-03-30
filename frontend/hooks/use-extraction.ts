"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiFetch, API_BASE } from "@/lib/api/client"
import type { DLQEntry } from "@/lib/api/types"

// ── Types ──────────────────────────────────────────────────────────────

export type SSEStatus = "connecting" | "connected" | "reconnecting" | "disconnected"

export interface ChapterProgress {
  chapter: number
  status: "pending" | "extracting" | "done" | "failed"
  entities: number
  duration_ms?: number
  error?: string
}

interface ExtractionSSEState {
  sseStatus: SSEStatus
  chapters: Map<number, ChapterProgress>
  totalEntities: number
  chaptersTotal: number
  chaptersDone: number
  error: string | null
  isDone: boolean
}

// ── SSE Hook ───────────────────────────────────────────────────────────

export function useExtractionSSE(bookId: string | null): ExtractionSSEState & { connect: () => void; disconnect: () => void } {
  const queryClient = useQueryClient()
  const esRef = useRef<EventSource | null>(null)
  const retryCountRef = useRef(0)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const keepaliveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [sseStatus, setSseStatus] = useState<SSEStatus>("disconnected")
  const [chapters, setChapters] = useState<Map<number, ChapterProgress>>(new Map())
  const [totalEntities, setTotalEntities] = useState(0)
  const [chaptersTotal, setChaptersTotal] = useState(0)
  const [chaptersDone, setChaptersDone] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [isDone, setIsDone] = useState(false)

  const resetKeepalive = useCallback(() => {
    if (keepaliveTimerRef.current) clearTimeout(keepaliveTimerRef.current)
    keepaliveTimerRef.current = setTimeout(() => {
      // No event for 60s — reconnect
      esRef.current?.close()
      setSseStatus("reconnecting")
      scheduleReconnect()
    }, 60_000)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const scheduleReconnect = useCallback(() => {
    const delay = Math.min(1000 * 2 ** retryCountRef.current, 30_000)
    retryCountRef.current += 1
    retryTimerRef.current = setTimeout(() => connectSSE(), delay)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookId])

  const connectSSE = useCallback(() => {
    if (!bookId) return
    esRef.current?.close()

    const es = new EventSource(`${API_BASE}/stream/extraction/${bookId}`)
    esRef.current = es
    setSseStatus("connecting")
    setError(null)

    es.onopen = () => {
      setSseStatus("connected")
      retryCountRef.current = 0
      resetKeepalive()
    }

    es.addEventListener("started", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data)
        setChaptersTotal(data.total ?? 0)
        setChaptersDone(0)
        setIsDone(false)
        resetKeepalive()
      } catch { /* ignore parse errors */ }
    })

    es.addEventListener("progress", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data)
        resetKeepalive()

        if (data.chapter) {
          setChapters((prev) => {
            const next = new Map(prev)
            next.set(data.chapter, {
              chapter: data.chapter,
              status: data.status === "failed" ? "failed" : "done",
              entities: data.entities_found ?? 0,
              duration_ms: data.duration_ms,
              error: data.error_message,
            })
            return next
          })
        }

        if (data.chapters_done != null) setChaptersDone(data.chapters_done)
        if (data.entities_found != null) setTotalEntities(data.entities_found)
      } catch { /* ignore */ }
    })

    es.addEventListener("done", () => {
      setIsDone(true)
      setSseStatus("disconnected")
      es.close()
      queryClient.invalidateQueries({ queryKey: ["book"] })
      queryClient.invalidateQueries({ queryKey: ["book-jobs"] })
    })

    es.addEventListener("error", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data)
        setError(data.message ?? "Extraction stopped due to an error")
        setSseStatus("disconnected")
      } catch {
        // Connection error — try reconnecting
        setSseStatus("reconnecting")
        scheduleReconnect()
      }
      es.close()
    })

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) {
        setSseStatus("reconnecting")
        scheduleReconnect()
      }
    }
  }, [bookId, queryClient, resetKeepalive, scheduleReconnect])

  const disconnect = useCallback(() => {
    esRef.current?.close()
    esRef.current = null
    if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
    if (keepaliveTimerRef.current) clearTimeout(keepaliveTimerRef.current)
    setSseStatus("disconnected")
  }, [])

  useEffect(() => {
    return () => disconnect()
  }, [disconnect])

  return {
    sseStatus,
    chapters,
    totalEntities,
    chaptersTotal,
    chaptersDone,
    error,
    isDone,
    connect: connectSSE,
    disconnect,
  }
}

// ── Extraction mutations ──────────────────────────────────────────────

export function useTriggerExtraction() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ bookId, chapters, provider, genre, language }: {
      bookId: string
      chapters?: number[]
      provider?: string
      genre?: string
      language?: string
    }) =>
      apiFetch(`/books/${bookId}/extract/v4`, {
        method: "POST",
        body: JSON.stringify({
          ...(chapters?.length ? { chapters } : {}),
          ...(provider ? { provider } : {}),
          ...(genre ? { genre } : {}),
          ...(language ? { language } : {}),
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["book-jobs"] })
    },
  })
}

export function useRetryChapter() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ bookId, chapter }: { bookId: string; chapter: number }) =>
      apiFetch(`/admin/dlq/retry/${bookId}/${chapter}`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dlq"] })
    },
  })
}

export function useDLQEntries(bookId: string | null) {
  return useQuery({
    queryKey: ["dlq", bookId],
    queryFn: () =>
      apiFetch<{ count: number; entries: DLQEntry[] }>(
        `/admin/dlq${bookId ? `?book_id=${bookId}` : ""}`
      ),
    enabled: !!bookId,
    staleTime: 10_000,
  })
}
