"use client"

import { useState } from "react"
import { ThumbsUp, ThumbsDown } from "lucide-react"
import { submitFeedback } from "@/lib/api/chat"

interface FeedbackButtonsProps {
  messageId: string
  threadId: string
  bookId?: string
}

export function FeedbackButtons({ messageId, threadId, bookId }: FeedbackButtonsProps) {
  const [rating, setRating] = useState<1 | -1 | null>(null)

  const handleFeedback = async (value: 1 | -1) => {
    if (rating !== null) return
    setRating(value)
    try {
      await submitFeedback({
        message_id: messageId,
        thread_id: threadId,
        rating: value,
        book_id: bookId,
      })
    } catch {
      setRating(null)
    }
  }

  return (
    <div className="flex items-center gap-1 mt-1">
      <button
        onClick={() => handleFeedback(1)}
        className={`p-1 rounded hover:bg-muted ${rating === 1 ? "text-green-500" : "text-muted-foreground"}`}
        disabled={rating !== null}
        aria-label="Thumbs up"
      >
        <ThumbsUp className="h-3.5 w-3.5" />
      </button>
      <button
        onClick={() => handleFeedback(-1)}
        className={`p-1 rounded hover:bg-muted ${rating === -1 ? "text-red-500" : "text-muted-foreground"}`}
        disabled={rating !== null}
        aria-label="Thumbs down"
      >
        <ThumbsDown className="h-3.5 w-3.5" />
      </button>
    </div>
  )
}
