"use client"

interface Annotation {
  start: number
  end: number
  type: string
  entityId?: string
}

interface ChapterContentProps {
  text: string
  annotations?: Annotation[]
}

/**
 * Renders chapter text as plain paragraphs split on double newlines.
 * Annotations are accepted but currently fall through to plain text rendering.
 */
export function ChapterContent({ text }: ChapterContentProps) {
  const paragraphs = text.split(/\n\n+/).filter((p) => p.trim().length > 0)

  return (
    <div className="space-y-4">
      {paragraphs.map((paragraph, i) => (
        <p
          key={i}
          className="font-serif text-lg leading-relaxed"
        >
          {paragraph}
        </p>
      ))}
    </div>
  )
}
