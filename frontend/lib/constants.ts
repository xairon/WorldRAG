export type EntityType =
  | "Character" | "Skill" | "Class" | "Event" | "Location"
  | "Item" | "System" | "Title" | "Level" | "Faction"
  | "Arc" | "Creature" | "Concept" | "Race" | "Prophecy"

export type UIStatus = "pending" | "parsing" | "ready" | "extracting" | "embedding" | "done" | "error" | "error_quota"

/** Tailwind color class per entity type (bg-, text-, border- prefix yourself) */
export const ENTITY_COLORS: Record<string, string> = {
  Character: "blue-500",
  Skill: "violet-500",
  Class: "amber-500",
  Event: "rose-500",
  Location: "emerald-500",
  Item: "orange-500",
  System: "cyan-500",
  Title: "fuchsia-500",
  Level: "lime-500",
  Faction: "teal-500",
  Arc: "slate-400",
  Creature: "red-500",
  Concept: "indigo-500",
  Race: "pink-500",
  Prophecy: "purple-500",
} as const

/** Hex colors for Sigma.js and recharts (not Tailwind classes) */
export const ENTITY_HEX: Record<string, string> = {
  Character: "#3b82f6",
  Skill: "#8b5cf6",
  Class: "#f59e0b",
  Event: "#f43f5e",
  Location: "#10b981",
  Item: "#f97316",
  System: "#06b6d4",
  Title: "#d946ef",
  Level: "#84cc16",
  Faction: "#14b8a6",
  Arc: "#94a3b8",
  Creature: "#ef4444",
  Concept: "#6366f1",
  Race: "#ec4899",
  Prophecy: "#a855f7",
} as const

export const ENTITY_HEX_FALLBACK = "#9ca3af" // gray-400

export const STATUS_CONFIG: Record<UIStatus, { color: string; hex: string; label: string }> = {
  pending:    { color: "gray-400",    hex: "#9ca3af", label: "Pending" },
  parsing:    { color: "blue-500",    hex: "#3b82f6", label: "Parsing" },
  ready:      { color: "slate-500",   hex: "#64748b", label: "Ready" },
  extracting: { color: "amber-500",   hex: "#f59e0b", label: "Extracting" },
  embedding:  { color: "cyan-500",    hex: "#06b6d4", label: "Embedding" },
  done:       { color: "emerald-500", hex: "#10b981", label: "Done" },
  error:      { color: "red-500",     hex: "#ef4444", label: "Error" },
  error_quota: { color: "orange-500", hex: "#f97316", label: "Quota Exceeded" },
} as const

/** Map backend ProcessingStatus values to frontend UIStatus */
export function mapBackendStatus(status: string): UIStatus {
  switch (status) {
    case "pending": return "pending"
    case "ingesting":
    case "chunking": return "parsing"
    case "completed": return "ready"
    case "extracting":
    case "reconciling":
    case "validating": return "extracting"
    case "embedding": return "embedding"
    case "extracted":
    case "embedded": return "done"
    case "error_quota": return "error_quota"
    case "failed":
    case "partial": return "error"
    default: return "pending"
  }
}

export function getEntityHex(type: string): string {
  return ENTITY_HEX[type] ?? ENTITY_HEX_FALLBACK
}
