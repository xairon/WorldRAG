import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Map entity label to a color for graph nodes and badges. */
export const LABEL_COLORS: Record<string, string> = {
  Character: "#6366f1",  // indigo
  Skill: "#10b981",      // emerald
  Class: "#f59e0b",      // amber
  Title: "#ec4899",      // pink
  Event: "#ef4444",      // red
  Location: "#3b82f6",   // blue
  Item: "#8b5cf6",       // violet
  Creature: "#f97316",   // orange
  Faction: "#14b8a6",    // teal
  Concept: "#64748b",    // slate
}

/** Map entity label to a Tailwind bg/text class for badges. */
export const LABEL_BADGE_CLASSES: Record<string, string> = {
  Character: "bg-indigo-500/15 text-indigo-400 border-indigo-500/25",
  Skill: "bg-emerald-500/15 text-emerald-400 border-emerald-500/25",
  Class: "bg-amber-500/15 text-amber-400 border-amber-500/25",
  Title: "bg-pink-500/15 text-pink-400 border-pink-500/25",
  Event: "bg-red-500/15 text-red-400 border-red-500/25",
  Location: "bg-blue-500/15 text-blue-400 border-blue-500/25",
  Item: "bg-violet-500/15 text-violet-400 border-violet-500/25",
  Creature: "bg-orange-500/15 text-orange-400 border-orange-500/25",
  Faction: "bg-teal-500/15 text-teal-400 border-teal-500/25",
  Concept: "bg-slate-500/15 text-slate-400 border-slate-500/25",
}

/** Fallback palette for dynamically induced entity types not in LABEL_COLORS. */
const FALLBACK_COLORS = [
  "#8b5cf6", "#f59e0b", "#14b8a6", "#f43f5e", "#6366f1",
  "#84cc16", "#e879f9", "#22d3ee", "#fb923c", "#a3e635",
]

/** Fallback Tailwind badge classes for unknown types. */
const FALLBACK_BADGE_CLASSES = [
  "bg-violet-500/15 text-violet-400 border-violet-500/25",
  "bg-amber-500/15 text-amber-400 border-amber-500/25",
  "bg-teal-500/15 text-teal-400 border-teal-500/25",
  "bg-rose-500/15 text-rose-400 border-rose-500/25",
  "bg-indigo-500/15 text-indigo-400 border-indigo-500/25",
  "bg-lime-500/15 text-lime-400 border-lime-500/25",
  "bg-fuchsia-500/15 text-fuchsia-400 border-fuchsia-500/25",
  "bg-cyan-500/15 text-cyan-400 border-cyan-500/25",
  "bg-orange-500/15 text-orange-400 border-orange-500/25",
  "bg-green-500/15 text-green-400 border-green-500/25",
]

function hashStringToIndex(str: string, max: number): number {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash + str.charCodeAt(i)) | 0
  }
  return Math.abs(hash) % max
}

export function labelColor(label: string): string {
  return LABEL_COLORS[label] ?? FALLBACK_COLORS[hashStringToIndex(label, FALLBACK_COLORS.length)]
}

export function labelBadgeClass(label: string): string {
  return LABEL_BADGE_CLASSES[label] ?? FALLBACK_BADGE_CLASSES[hashStringToIndex(label, FALLBACK_BADGE_CLASSES.length)]
}

/** Status badge styling. */
export function statusColor(status: string): string {
  switch (status) {
    case "completed":
    case "embedded":
    case "extracted":
      return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
    case "ingesting":
    case "chunking":
    case "extracting":
    case "reconciling":
    case "validating":
    case "embedding":
      return "bg-amber-500/20 text-amber-400 border-amber-500/30"
    case "failed":
      return "bg-red-500/20 text-red-400 border-red-500/30"
    case "pending":
    case "queued":
      return "bg-blue-500/20 text-blue-400 border-blue-500/30"
    default:
      return "bg-slate-500/20 text-slate-400 border-slate-500/30"
  }
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat().format(n)
}
