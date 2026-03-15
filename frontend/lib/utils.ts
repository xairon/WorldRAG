import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatNumber(n: number): string {
  return n.toLocaleString("en-US")
}

// Re-export from constants for backwards compat during migration
export { ENTITY_COLORS, ENTITY_HEX, STATUS_CONFIG, mapBackendStatus, getEntityHex } from "./constants"

import { ENTITY_HEX as _ENTITY_HEX } from "./constants"
/** @deprecated Use ENTITY_HEX instead */
export const LABEL_COLORS = _ENTITY_HEX
