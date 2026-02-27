"use client"

import type { ParagraphData } from "@/lib/api/reader"

interface ParagraphRendererProps {
  paragraph: ParagraphData
  children?: React.ReactNode
}

export function ParagraphRenderer({ paragraph, children }: ParagraphRendererProps) {
  const content = children || paragraph.text

  switch (paragraph.type) {
    case "header":
      return (
        <h3 className="text-xl font-semibold text-slate-200 mt-10 mb-4 first:mt-0 text-center tracking-wide">
          {content}
        </h3>
      )

    case "dialogue":
      return (
        <p className="reader-paragraph text-[1.05rem] leading-[1.9] text-slate-200 my-0 indent-8 font-serif">
          {paragraph.speaker && (
            <span className="text-xs text-indigo-400/60 font-sans font-medium mr-2 inline-block align-baseline" style={{ textIndent: 0 }}>
              {paragraph.speaker}
            </span>
          )}
          {content}
        </p>
      )

    case "blue_box":
      return (
        <div className="my-6 mx-auto max-w-lg">
          <div className="relative rounded-lg border border-cyan-500/40 bg-gradient-to-b from-cyan-950/40 to-slate-950/60 px-5 py-4 shadow-[0_0_15px_rgba(6,182,212,0.08)]">
            <div className="absolute top-0 left-0 w-3 h-3 border-t-2 border-l-2 border-cyan-400/50 rounded-tl-lg" />
            <div className="absolute top-0 right-0 w-3 h-3 border-t-2 border-r-2 border-cyan-400/50 rounded-tr-lg" />
            <div className="absolute bottom-0 left-0 w-3 h-3 border-b-2 border-l-2 border-cyan-400/50 rounded-bl-lg" />
            <div className="absolute bottom-0 right-0 w-3 h-3 border-b-2 border-r-2 border-cyan-400/50 rounded-br-lg" />
            <div className="text-[0.9rem] leading-relaxed text-cyan-100 font-mono text-center whitespace-pre-line">
              {content}
            </div>
          </div>
        </div>
      )

    case "scene_break":
      return (
        <div className="my-8 flex items-center justify-center gap-3">
          <div className="h-px w-12 bg-gradient-to-r from-transparent to-slate-600" />
          <span className="text-slate-500 text-lg tracking-[0.4em]">&#10045; &#10045; &#10045;</span>
          <div className="h-px w-12 bg-gradient-to-l from-transparent to-slate-600" />
        </div>
      )

    case "narration":
    default:
      return (
        <p className="reader-paragraph text-[1.05rem] leading-[1.9] text-slate-200 my-0 indent-8 font-serif">
          {content}
        </p>
      )
  }
}
