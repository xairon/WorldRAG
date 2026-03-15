"use client"

import { useEffect, useRef, useCallback } from "react"
import { useExtractionStore } from "@/stores/extraction-store"

export function useExtractionStream(bookId: string | null) {
  const eventSourceRef = useRef<EventSource | null>(null)
  const status = useExtractionStore((s) => s.status)
  const feedMessages = useExtractionStore((s) => s.feedMessages)
  const chaptersDone = useExtractionStore((s) => s.chaptersDone)
  const chaptersTotal = useExtractionStore((s) => s.chaptersTotal)
  const entitiesFound = useExtractionStore((s) => s.entitiesFound)

  const connect = useCallback(() => {
    if (!bookId) return
    eventSourceRef.current?.close()
    const es = new EventSource(`/api/stream/extraction/${bookId}`)
    eventSourceRef.current = es
    const store = useExtractionStore.getState()
    store.setStatus("running")

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        const s = useExtractionStore.getState()
        if (data.status === "started") {
          s.setProgress({ chaptersTotal: data.total, chaptersDone: 0 })
        } else if (data.status === "progress") {
          s.setProgress({
            chaptersDone: data.chapters_done,
            entitiesFound: data.entities_found ?? s.entitiesFound,
          })
        } else if (data.status === "done") {
          s.setStatus("done")
          es.close()
        }
      } catch {}
    }

    es.onerror = () => {
      useExtractionStore.getState().setStatus("error")
      es.close()
    }
  }, [bookId])

  const disconnect = useCallback(() => {
    eventSourceRef.current?.close()
    eventSourceRef.current = null
  }, [])

  useEffect(() => {
    return () => disconnect()
  }, [disconnect])

  return { connect, disconnect, status, feedMessages, chaptersDone, chaptersTotal, entitiesFound }
}
