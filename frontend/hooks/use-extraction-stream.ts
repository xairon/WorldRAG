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
  const errorDetail = useExtractionStore((s) => s.errorDetail)

  const connect = useCallback(() => {
    if (!bookId) return
    eventSourceRef.current?.close()
    const es = new EventSource(`/api/stream/extraction/${bookId}`)
    eventSourceRef.current = es
    const store = useExtractionStore.getState()
    store.setStatus("running")
    store.setErrorDetail(null)

    es.addEventListener("started", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data)
        const s = useExtractionStore.getState()
        s.setProgress({ chaptersTotal: data.total, chaptersDone: 0 })
      } catch {}
    })

    es.addEventListener("progress", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data)
        const s = useExtractionStore.getState()
        s.setProgress({
          chaptersDone: data.chapters_done,
          entitiesFound: data.entities_found ?? s.entitiesFound,
        })
        // Feed message
        if (data.chapter) {
          const detail = data.detail
          const parts: string[] = []
          if (detail?.characters) parts.push(`${detail.characters} chars`)
          if (detail?.events) parts.push(`${detail.events} events`)
          if (detail?.locations) parts.push(`${detail.locations} locs`)
          if (detail?.items) parts.push(`${detail.items} items`)
          s.addFeedMessage({
            time: new Date().toLocaleTimeString(),
            chapter: data.chapter,
            type: data.status === "extracted" ? "success" : "error",
            name: parts.length > 0 ? parts.join(", ") : data.status,
          })
        }
      } catch {}
    })

    es.addEventListener("done", () => {
      useExtractionStore.getState().setStatus("done")
      es.close()
    })

    es.addEventListener("error", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data)
        const s = useExtractionStore.getState()
        s.setErrorDetail({
          type: data.error_type ?? "unknown",
          provider: data.provider ?? "",
          message: data.message ?? "Extraction stopped due to an error",
        })
        s.setProgress({ chaptersDone: data.chapters_done ?? s.chaptersDone })
        s.setStatus("error_quota")
      } catch {}
      es.close()
    })

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

  return { connect, disconnect, status, feedMessages, chaptersDone, chaptersTotal, entitiesFound, errorDetail }
}
