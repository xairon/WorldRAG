"use client"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { CharacterStateSnapshot } from "@/lib/api/characters"

interface CharacterHeaderProps {
  snapshot: CharacterStateSnapshot
}

export function CharacterHeader({ snapshot }: CharacterHeaderProps) {
  const { character_name, role, species, level, classes, description, aliases } = snapshot
  const activeClass = classes.find((c) => c.is_active)

  return (
    <div className="rounded-xl bg-slate-900/50 border border-slate-800 p-6">
      <div className="flex flex-col gap-3">
        {/* Name + Aliases */}
        <div>
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight">
            {character_name}
          </h1>
          {aliases.length > 0 && (
            <p className="text-xs text-slate-500 mt-1">
              aka {aliases.join(", ")}
            </p>
          )}
        </div>

        {/* Badges row */}
        <div className="flex flex-wrap items-center gap-2">
          {role && (
            <Badge
              variant="outline"
              className="border-indigo-500/25 bg-indigo-500/10 text-indigo-400 text-xs"
            >
              {role}
            </Badge>
          )}
          {species && (
            <Badge
              variant="outline"
              className="border-slate-700 text-slate-400 text-xs"
            >
              {species}
            </Badge>
          )}
          {level.level !== null && (
            <Badge
              variant="outline"
              className={cn(
                "font-mono text-xs",
                "border-amber-500/25 bg-amber-500/10 text-amber-400",
              )}
            >
              Lv. {level.level}
              {level.realm && (
                <span className="text-amber-500/70 ml-1">
                  {" \u2022 "}{level.realm}
                </span>
              )}
            </Badge>
          )}
          {activeClass && (
            <Badge
              variant="outline"
              className="border-emerald-500/25 bg-emerald-500/10 text-emerald-400 text-xs"
            >
              {activeClass.name}
              {activeClass.tier !== null && (
                <span className="text-emerald-500/70 ml-1">T{activeClass.tier}</span>
              )}
            </Badge>
          )}
        </div>

        {/* Description */}
        {description && (
          <p className="text-sm text-slate-400 leading-relaxed line-clamp-2 max-w-2xl">
            {description}
          </p>
        )}
      </div>
    </div>
  )
}
