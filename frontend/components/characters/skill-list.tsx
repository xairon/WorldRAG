"use client"

import { useMemo, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { SkillSnapshot } from "@/lib/api/characters"

interface SkillListProps {
  skills: SkillSnapshot[]
}

const RANK_COLORS: Record<string, string> = {
  common: "border-slate-600 bg-slate-500/10 text-slate-400",
  uncommon: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
  rare: "border-blue-500/30 bg-blue-500/10 text-blue-400",
  epic: "border-violet-500/30 bg-violet-500/10 text-violet-400",
  legendary: "border-amber-500/30 bg-amber-500/10 text-amber-400",
  unique: "border-rose-500/30 bg-rose-500/10 text-rose-400",
}

function rankClass(rank: string): string {
  return RANK_COLORS[rank.toLowerCase()] ?? RANK_COLORS.common
}

export function SkillList({ skills }: SkillListProps) {
  const [typeFilter, setTypeFilter] = useState<string | null>(null)

  // Gather unique skill types for filtering
  const skillTypes = useMemo(() => {
    const types = new Set<string>()
    for (const s of skills) {
      if (s.skill_type) types.add(s.skill_type)
    }
    return Array.from(types).sort()
  }, [skills])

  // Filter and sort by acquired chapter
  const filtered = useMemo(() => {
    const list = typeFilter
      ? skills.filter((s) => s.skill_type === typeFilter)
      : skills
    return [...list].sort((a, b) => (a.acquired_chapter ?? 0) - (b.acquired_chapter ?? 0))
  }, [skills, typeFilter])

  if (skills.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-8 text-center">
        <p className="text-sm text-slate-500">No skills acquired yet.</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Type filter */}
      {skillTypes.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setTypeFilter(null)}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium transition-colors",
              typeFilter === null
                ? "bg-indigo-500/15 text-indigo-400 border border-indigo-500/25"
                : "text-slate-500 hover:text-slate-300 border border-slate-800 hover:border-slate-700",
            )}
          >
            All ({skills.length})
          </button>
          {skillTypes.map((t) => (
            <button
              key={t}
              onClick={() => setTypeFilter(typeFilter === t ? null : t)}
              className={cn(
                "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                typeFilter === t
                  ? "bg-indigo-500/15 text-indigo-400 border border-indigo-500/25"
                  : "text-slate-500 hover:text-slate-300 border border-slate-800 hover:border-slate-700",
              )}
            >
              {t}
            </button>
          ))}
        </div>
      )}

      {/* Skill cards */}
      <div className="space-y-2">
        {filtered.map((skill) => (
          <div
            key={skill.name}
            className="rounded-xl bg-slate-900/50 border border-slate-800 px-4 py-3 flex items-start justify-between gap-4"
          >
            <div className="flex flex-col gap-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-medium text-slate-200">
                  {skill.name}
                </span>
                <Badge
                  variant="outline"
                  className={cn("text-[10px]", rankClass(skill.rank))}
                >
                  {skill.rank}
                </Badge>
                {skill.skill_type && (
                  <Badge
                    variant="outline"
                    className="text-[10px] border-slate-700 text-slate-500"
                  >
                    {skill.skill_type}
                  </Badge>
                )}
              </div>
              {skill.description && (
                <p className="text-xs text-slate-500 line-clamp-2">
                  {skill.description}
                </p>
              )}
            </div>
            {skill.acquired_chapter !== null && (
              <span className="text-[10px] text-slate-600 font-mono whitespace-nowrap mt-0.5">
                Ch. {skill.acquired_chapter}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
