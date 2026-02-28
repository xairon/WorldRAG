"use client"

import type { ParagraphData } from "@/lib/api/reader"
import type { ReaderTheme } from "@/hooks/use-reader-settings"
import { THEME_STYLES } from "@/hooks/use-reader-settings"

interface ParagraphRendererProps {
  paragraph: ParagraphData
  children?: React.ReactNode
  theme?: ReaderTheme
  fontSize?: number
  lineHeight?: number
  fontFamily?: "serif" | "sans"
}

export function ParagraphRenderer({
  paragraph,
  children,
  theme = "night",
  fontSize = 18,
  lineHeight = 1.8,
  fontFamily = "serif",
}: ParagraphRendererProps) {
  const content = children || paragraph.text
  const t = THEME_STYLES[theme]
  const font = fontFamily === "serif"
    ? '"Literata", "Georgia", "Cambria", "Times New Roman", serif'
    : '"Inter", system-ui, -apple-system, sans-serif'

  const baseStyle = {
    fontSize: `${fontSize}px`,
    lineHeight,
    color: t.text,
    fontFamily: font,
  }

  switch (paragraph.type) {
    case "header":
      return (
        <h3
          style={{
            fontSize: `${Math.round(fontSize * 1.3)}px`,
            lineHeight: 1.4,
            color: t.heading,
            fontFamily: font,
            fontWeight: 600,
            textAlign: "center" as const,
            letterSpacing: "0.02em",
            marginTop: "2.5em",
            marginBottom: "1em",
          }}
        >
          {content}
        </h3>
      )

    case "dialogue":
      return (
        <p style={{ ...baseStyle, textIndent: "1.5em", margin: "0.15em 0" }}>
          {paragraph.speaker && (
            <span
              style={{
                fontSize: `${Math.round(fontSize * 0.7)}px`,
                color: t.speaker,
                fontFamily: '"Inter", system-ui, sans-serif',
                fontWeight: 500,
                marginRight: "0.5em",
                textIndent: "0",
                display: "inline",
                opacity: 0.7,
              }}
            >
              {paragraph.speaker}
            </span>
          )}
          {content}
        </p>
      )

    case "blue_box":
      return (
        <div style={{ margin: "1.5em auto", maxWidth: "480px" }}>
          <div
            style={{
              position: "relative",
              borderRadius: "8px",
              border: `1px solid ${t.bluebox.border}`,
              background: t.bluebox.bg,
              padding: "1em 1.25em",
              boxShadow: `0 0 20px ${t.bluebox.border}15`,
            }}
          >
            {/* Corner decorations */}
            {(["top-left", "top-right", "bottom-left", "bottom-right"] as const).map((pos) => {
              const [v, h] = pos.split("-")
              return (
                <div
                  key={pos}
                  style={{
                    position: "absolute",
                    [v]: 0,
                    [h]: 0,
                    width: "10px",
                    height: "10px",
                    [`border${v === "top" ? "Top" : "Bottom"}`]: `2px solid ${t.bluebox.corner}`,
                    [`border${h === "left" ? "Left" : "Right"}`]: `2px solid ${t.bluebox.corner}`,
                    [`border${v === "top" ? "Top" : "Bottom"}${h === "left" ? "Left" : "Right"}Radius`]: "8px",
                    opacity: 0.6,
                  }}
                />
              )
            })}
            <div
              style={{
                fontSize: `${Math.round(fontSize * 0.85)}px`,
                lineHeight: 1.6,
                color: t.bluebox.text,
                fontFamily: '"SF Mono", "Fira Code", ui-monospace, monospace',
                textAlign: "center" as const,
                whiteSpace: "pre-line" as const,
              }}
            >
              {content}
            </div>
          </div>
        </div>
      )

    case "scene_break":
      return (
        <div
          style={{
            margin: "2em 0",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "12px",
          }}
        >
          <div
            style={{
              height: "1px",
              width: "48px",
              background: `linear-gradient(to right, transparent, ${t.sceneBreak})`,
            }}
          />
          <span
            style={{
              color: t.sceneBreak,
              fontSize: "1.1em",
              letterSpacing: "0.4em",
              opacity: 0.7,
            }}
          >
            &#10045; &#10045; &#10045;
          </span>
          <div
            style={{
              height: "1px",
              width: "48px",
              background: `linear-gradient(to left, transparent, ${t.sceneBreak})`,
            }}
          />
        </div>
      )

    case "narration":
    default:
      return (
        <p style={{ ...baseStyle, textIndent: "1.5em", margin: "0.15em 0" }}>
          {content}
        </p>
      )
  }
}
