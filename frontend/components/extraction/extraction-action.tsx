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
  disabled?: boolean
}

export function ExtractionAction({
  bookStatus,
  onStart,
  onCancel,
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
          <RotateCcw className="mr-2 h-4 w-4" />
          Re-extract
        </Button>
      )
    case "error_quota":
    case "error":
      return (
        <Button onClick={onStart} disabled={disabled}>
          <RotateCcw className="mr-2 h-4 w-4" />
          Retry
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
