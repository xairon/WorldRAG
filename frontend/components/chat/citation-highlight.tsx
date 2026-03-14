"use client"

interface CitationHighlightProps {
  text: string
}

export function CitationHighlight({ text }: CitationHighlightProps) {
  const parts = text.split(/(\[Ch\.\d+(?:,\s*§\d+)?\])/g)

  return (
    <span>
      {parts.map((part, i) => {
        const match = part.match(/^\[Ch\.(\d+)(?:,\s*§(\d+))?\]$/)
        if (match) {
          return (
            <span
              key={i}
              className="cursor-help rounded bg-primary/10 px-1 text-primary font-medium text-xs"
              title={`Chapter ${match[1]}${match[2] ? `, paragraph ${match[2]}` : ""}`}
            >
              {part}
            </span>
          )
        }
        return <span key={i}>{part}</span>
      })}
    </span>
  )
}
