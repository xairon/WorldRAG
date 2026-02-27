"use client"

import { useMemo } from "react"
import { cn, labelColor, labelBadgeClass } from "@/lib/utils"
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card"
import { EntityBadge } from "@/components/shared/entity-badge"
import { CharacterHoverContent } from "@/components/reader/character-hover-content"
import type { EntityAnnotation } from "@/lib/api/reader"

interface AnnotatedTextProps {
  text: string
  annotations: EntityAnnotation[]
  mode: "annotated" | "clean" | "focus"
  focusType?: string // only show this entity type when mode === "focus"
  bookId?: string
  chapter?: number
  className?: string
}

interface TextSegment {
  text: string
  annotation?: EntityAnnotation
}

/**
 * Build non-overlapping text segments from annotations.
 * When annotations overlap, the longest span wins.
 */
function buildSegments(text: string, annotations: EntityAnnotation[]): TextSegment[] {
  if (annotations.length === 0) {
    return [{ text }]
  }

  // Filter valid annotations and sort by start offset
  const valid = annotations
    .filter(
      (a) =>
        a.char_offset_start >= 0 &&
        a.char_offset_end > a.char_offset_start &&
        a.char_offset_end <= text.length,
    )
    .sort((a, b) => a.char_offset_start - b.char_offset_start)

  // Remove overlaps: keep the longest span when overlapping
  const resolved: EntityAnnotation[] = []
  for (const ann of valid) {
    const last = resolved[resolved.length - 1]
    if (last && ann.char_offset_start < last.char_offset_end) {
      // Overlap: keep the longer one
      if (ann.char_offset_end - ann.char_offset_start > last.char_offset_end - last.char_offset_start) {
        resolved[resolved.length - 1] = ann
      }
      // else keep last
    } else {
      resolved.push(ann)
    }
  }

  // Build segments
  const segments: TextSegment[] = []
  let cursor = 0

  for (const ann of resolved) {
    // Plain text before this annotation
    if (ann.char_offset_start > cursor) {
      segments.push({ text: text.slice(cursor, ann.char_offset_start) })
    }

    // Annotated segment
    segments.push({
      text: text.slice(ann.char_offset_start, ann.char_offset_end),
      annotation: ann,
    })

    cursor = ann.char_offset_end
  }

  // Remaining text
  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor) })
  }

  return segments
}

function getUnderlineStyle(mentionType: string | undefined): string {
  switch (mentionType) {
    case "alias":
      return "dashed"
    case "pronoun":
      return "dotted"
    default: // langextract, direct_name
      return "solid"
  }
}

export function AnnotatedText({
  text,
  annotations,
  mode,
  focusType,
  bookId,
  chapter,
  className,
}: AnnotatedTextProps) {
  const filteredAnnotations = useMemo(() => {
    if (mode === "clean") return []
    if (mode === "focus" && focusType) {
      return annotations.filter((a) => a.entity_type === focusType)
    }
    return annotations
  }, [annotations, mode, focusType])

  const segments = useMemo(
    () => buildSegments(text, filteredAnnotations),
    [text, filteredAnnotations],
  )

  // Use span (not div) so it can be placed inside <p> from ParagraphRenderer
  return (
    <span className={cn(className)}>
      {segments.map((seg, i) =>
        seg.annotation ? (
          <AnnotatedSpan key={i} segment={seg} annotation={seg.annotation} bookId={bookId} chapter={chapter} />
        ) : (
          <span key={i}>{seg.text}</span>
        ),
      )}
    </span>
  )
}

function AnnotatedSpan({
  segment,
  annotation,
  bookId,
  chapter,
}: {
  segment: TextSegment
  annotation: EntityAnnotation
  bookId?: string
  chapter?: number
}) {
  const color = labelColor(annotation.entity_type)
  const isCharacter = annotation.entity_type === "Character"

  return (
    <HoverCard openDelay={200} closeDelay={100}>
      <HoverCardTrigger asChild>
        <span
          className="cursor-pointer rounded-sm px-0.5 -mx-0.5 transition-colors hover:brightness-125"
          style={{
            backgroundColor: `${color}15`,
            borderBottom: `2px ${getUnderlineStyle(annotation.mention_type)} ${color}40`,
            color: color,
          }}
        >
          {segment.text}
        </span>
      </HoverCardTrigger>
      <HoverCardContent
        side="top"
        align="start"
        className="w-64 p-3 space-y-2"
      >
        {isCharacter ? (
          <CharacterHoverContent
            characterName={annotation.entity_name}
            bookId={bookId}
            chapter={chapter}
          />
        ) : (
          <>
            <div className="flex items-center gap-2">
              <EntityBadge
                name={annotation.entity_name}
                type={annotation.entity_type}
                size="sm"
              />
            </div>
            {annotation.mention_type && annotation.mention_type !== "langextract" && (
              <span className="text-[10px] text-slate-500 uppercase tracking-wider">
                {annotation.mention_type.replace("_", " ")}
              </span>
            )}
            {annotation.extraction_text && (
              <p className="text-xs text-slate-500 leading-relaxed line-clamp-3">
                {annotation.extraction_text}
              </p>
            )}
          </>
        )}
      </HoverCardContent>
    </HoverCard>
  )
}
