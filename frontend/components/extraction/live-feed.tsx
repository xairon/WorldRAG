"use client"

import { useRef, useEffect, useCallback } from "react"
import { getEntityHex } from "@/lib/constants"
import type { FeedMessage } from "@/stores/extraction-store"

interface LiveFeedProps {
  messages: FeedMessage[]
}

export function LiveFeed({ messages }: LiveFeedProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const userScrolledRef = useRef(false)

  const handleScroll = useCallback(() => {
    const el = containerRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24
    userScrolledRef.current = !atBottom
  }, [])

  useEffect(() => {
    const el = containerRef.current
    if (!el || userScrolledRef.current) return
    el.scrollTop = el.scrollHeight
  }, [messages])

  if (messages.length === 0) return null

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="h-[200px] overflow-auto rounded-md border bg-muted/30 p-3"
    >
      {messages.map((msg, i) => (
        <div key={i} className="font-mono text-xs leading-relaxed">
          <span className="text-muted-foreground">{msg.time}</span>{" "}
          <span className="text-muted-foreground">Ch.{msg.chapter}</span>
          <span className="text-muted-foreground">{" \u2192 "}</span>
          <span style={{ color: getEntityHex(msg.type) }}>{msg.type}</span>
          {": "}
          <span>{msg.name}</span>
        </div>
      ))}
    </div>
  )
}
