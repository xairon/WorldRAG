"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { API_BASE } from "@/lib/api/client"

export interface ExtractionEvent {
  chapter: number
  total: number
  status: string
  entities_found: number
  chapters_done: number
}

interface UseExtractionProgressReturn {
  events: ExtractionEvent[]
  isConnected: boolean
  isDone: boolean
  latestEvent: ExtractionEvent | null
  progress: number // 0-100
  connect: (bookId: string) => void
  disconnect: () => void
}

export function useExtractionProgress(): UseExtractionProgressReturn {
  const [events, setEvents] = useState<ExtractionEvent[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [isDone, setIsDone] = useState(false)
  const controllerRef = useRef<AbortController | null>(null)

  const disconnect = useCallback(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
    setIsConnected(false)
  }, [])

  const connect = useCallback((bookId: string) => {
    disconnect()
    setEvents([])
    setIsDone(false)
    setIsConnected(true)

    const controller = new AbortController()
    controllerRef.current = controller
    const url = `${API_BASE}/stream/extraction/${bookId}`

    ;(async () => {
      try {
        const res = await fetch(url, { signal: controller.signal })
        if (!res.ok) {
          setIsConnected(false)
          return
        }

        const reader = res.body?.getReader()
        if (!reader) return

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
              if (!rawData || currentEvent === "keepalive") {
                currentEvent = ""
                continue
              }
              try {
                const data = JSON.parse(rawData)
                if (currentEvent === "progress") {
                  setEvents((prev) => [...prev, data as ExtractionEvent])
                } else if (currentEvent === "done") {
                  setIsDone(true)
                  setIsConnected(false)
                }
              } catch {
                // skip non-JSON
              }
              currentEvent = ""
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setIsConnected(false)
        }
      }
    })()
  }, [disconnect])

  useEffect(() => {
    return () => {
      controllerRef.current?.abort()
    }
  }, [])

  const latestEvent = events.length > 0 ? events[events.length - 1] : null
  const progress = latestEvent
    ? Math.round((latestEvent.chapters_done / latestEvent.total) * 100)
    : 0

  return { events, isConnected, isDone, latestEvent, progress, connect, disconnect }
}
