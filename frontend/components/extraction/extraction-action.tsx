"use client"

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
  hasProfile,
  isFirstBook,
  onStart,
  onCancel,
  disabled = false,
}: ExtractionActionProps) {
  const uiStatus = mapBackendStatus(bookStatus)

  switch (uiStatus) {
    case "ready":
      return (
        <Button onClick={onStart} disabled={disabled}>
          {isFirstBook && !hasProfile ? "Configure & Extract" : "Start extraction"}
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
