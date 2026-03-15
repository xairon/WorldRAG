"use client"

import { mapBackendStatus } from "@/lib/constants"
import { StatusBadge } from "@/components/shared/status-badge"

export function BookStatusBadge({ status }: { status: string }) {
  return <StatusBadge status={mapBackendStatus(status)} />
}
