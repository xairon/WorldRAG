"use client"

import type { ParagraphData } from "@/lib/api/reader"

interface ParagraphRendererProps {
  paragraph: ParagraphData
  children?: React.ReactNode  // For annotated content overlay
}

export function ParagraphRenderer({ paragraph, children }: ParagraphRendererProps) {
  const content = children || paragraph.text

  switch (paragraph.type) {
    case "header":
      return (
        <h3 className="text-lg font-semibold text-slate-200 mt-8 mb-3 first:mt-0">
          {content}
        </h3>
      )

    case "dialogue":
      return (
        <div className="pl-4 border-l-2 border-indigo-500/30 my-2">
          {paragraph.speaker && (
            <span className="text-xs text-indigo-400/70 font-medium block mb-0.5">
              {paragraph.speaker}
            </span>
          )}
          <p className="text-sm leading-7 text-slate-300 italic">
            {content}
          </p>
        </div>
      )

    case "blue_box":
      return (
        <div className="my-4 rounded-lg border border-cyan-500/30 bg-cyan-500/5 px-4 py-3">
          <p className="text-sm leading-6 text-cyan-200 font-mono">
            {content}
          </p>
        </div>
      )

    case "scene_break":
      return (
        <div className="my-6 flex justify-center">
          <span className="text-slate-600 tracking-[0.5em]">***</span>
        </div>
      )

    case "narration":
    default:
      return (
        <p className="text-sm leading-7 text-slate-300 my-2">
          {content}
        </p>
      )
  }
}
