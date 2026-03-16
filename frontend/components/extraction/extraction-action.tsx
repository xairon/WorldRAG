"use client"

import { RotateCcw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { mapBackendStatus } from "@/lib/constants"

interface ExtractionActionProps {
  bookStatus: string
  hasProfile: boolean
  isFirstBook: boolean
  onStart: () => void
  onCancel: () => void
  onRetryOllama: () => void
  disabled?: boolean
}

export function ExtractionAction({
  bookStatus,
  hasProfile,
  isFirstBook,
  onStart,
  onCancel,
  onRetryOllama,
  disabled = false,
}: ExtractionActionProps) {
  const uiStatus = mapBackendStatus(bookStatus)

  switch (uiStatus) {
    case "ready":
      return (
        <Button onClick={onStart} disabled={disabled}>
          Start extraction
        </Button>
      )
    case "extracting":
    case "embedding":
      return (
        <Button variant="destructive" onClick={onCancel} disabled={disabled}>
          Cancel
        </Button>
      )
    case "done":
      return (
        <Button variant="outline" onClick={onStart} disabled={disabled}>
          Re-extract
        </Button>
      )
    case "error_quota":
      return (
        <div className="flex items-center gap-2">
          <Button onClick={onRetryOllama} disabled={disabled}>
            <RotateCcw className="mr-2 h-4 w-4" />
            Retry with Ollama
          </Button>
          <Button variant="outline" onClick={onStart} disabled={disabled}>
            Retry with Gemini
          </Button>
        </div>
      )
    case "error":
      return (
        <Button onClick={onStart} disabled={disabled}>
          Resume
        </Button>
      )
    default:
      return (
        <Button disabled>
          Waiting...
        </Button>
      )
  }
}
