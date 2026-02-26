"use client"

import Link from "next/link"
import { useCharacterSummary } from "@/hooks/useCharacterState"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"

interface CharacterHoverContentProps {
  characterName: string
  bookId?: string
  chapter?: number
}

export function CharacterHoverContent({
  characterName,
  bookId,
  chapter,
}: CharacterHoverContentProps) {
  const { data, error, isLoading } = useCharacterSummary(
    characterName,
    bookId ?? null,
    chapter ?? null,
  )

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-5 w-32" />
        <div className="flex gap-2">
          <Skeleton className="h-5 w-16" />
          <Skeleton className="h-5 w-20" />
        </div>
        <Skeleton className="h-8 w-full" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div>
        <p className="text-sm font-semibold text-slate-200">{characterName}</p>
      </div>
    )
  }

  const profileParams = new URLSearchParams()
  if (bookId) profileParams.set("book_id", bookId)
  if (chapter !== undefined) profileParams.set("chapter", String(chapter))
  const profileQs = profileParams.toString()
  const profileHref = `/characters/${encodeURIComponent(data.canonical_name || data.name)}${profileQs ? `?${profileQs}` : ""}`

  return (
    <div className="space-y-2">
      {/* Character name */}
      <p className="text-sm font-semibold text-slate-200">
        {data.canonical_name || data.name}
      </p>

      {/* Level badge + active class */}
      <div className="flex items-center gap-2 flex-wrap">
        {data.level != null && (
          <Badge
            variant="outline"
            className="bg-indigo-500/10 text-indigo-400 border-indigo-500/20 text-[11px] px-1.5 py-0"
          >
            Lv. {data.level}
            {data.realm ? ` \u00b7 ${data.realm}` : ""}
          </Badge>
        )}
        {data.active_class && (
          <span className="text-xs text-slate-400">{data.active_class}</span>
        )}
      </div>

      {/* Top skills */}
      {data.top_skills.length > 0 && (
        <div className="flex items-center gap-1 flex-wrap">
          {data.top_skills.slice(0, 3).map((skill) => (
            <span
              key={skill}
              className="inline-flex items-center rounded-full bg-slate-800 text-slate-400 text-[10px] px-1.5 py-0.5 border border-slate-700"
            >
              {skill}
            </span>
          ))}
        </div>
      )}

      {/* Description */}
      {data.description && (
        <p className="text-xs text-slate-500 leading-relaxed line-clamp-2">
          {data.description}
        </p>
      )}

      {/* Full character sheet link */}
      <Link
        href={profileHref}
        className="block text-[11px] text-indigo-400 hover:text-indigo-300 transition-colors"
      >
        Full Character Sheet &rarr;
      </Link>
    </div>
  )
}
