import { clsx, type ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
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
};

export function labelColor(label: string): string {
  return LABEL_COLORS[label] ?? "#94a3b8";
}

/** Status badge styling. */
export function statusColor(status: string): string {
  switch (status) {
    case "completed":
    case "extracted":
      return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
    case "ingesting":
    case "chunking":
    case "extracting":
      return "bg-amber-500/20 text-amber-400 border-amber-500/30";
    case "failed":
      return "bg-red-500/20 text-red-400 border-red-500/30";
    default:
      return "bg-slate-500/20 text-slate-400 border-slate-500/30";
  }
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat().format(n);
}
