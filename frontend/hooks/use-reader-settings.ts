"use client"

import { useState, useEffect, useCallback } from "react"

export type ReaderTheme = "white" | "sepia" | "night"
export type ReaderFont = "serif" | "sans"

export interface ReaderSettings {
  theme: ReaderTheme
  fontSize: number
  fontFamily: ReaderFont
  lineHeight: number
  annotations: boolean
}

const DEFAULTS: ReaderSettings = {
  theme: "night",
  fontSize: 18,
  fontFamily: "serif",
  lineHeight: 1.9,
  annotations: true,
}

const STORAGE_KEY = "worldrag-reader-settings"

export const FONT_SIZES = [14, 16, 18, 20, 22] as const
export const LINE_HEIGHTS = [1.5, 1.7, 1.9, 2.1] as const

export const THEME_STYLES = {
  white: {
    bg: "#ffffff",
    text: "#1c1917",
    textMuted: "#78716c",
    border: "#e7e5e4",
    surface: "#f5f5f4",
    heading: "#0c0a09",
    speaker: "#7c3aed",
    bluebox: { border: "#0891b2", bg: "#f0fdfa", text: "#134e4a", corner: "#06b6d4" },
    sceneBreak: "#d6d3d1",
    selectBg: "#dbeafe",
    annotationBgOpacity: "18",
    annotationBorderOpacity: "70",
  },
  sepia: {
    bg: "#f4ecd8",
    text: "#44302a",
    textMuted: "#8b7355",
    border: "#d4c5a9",
    surface: "#efe6d0",
    heading: "#2c1810",
    speaker: "#7e4a1e",
    bluebox: { border: "#92713c", bg: "#fef9ee", text: "#78350f", corner: "#b8860b" },
    sceneBreak: "#c4b89a",
    selectBg: "#fde68a",
    annotationBgOpacity: "18",
    annotationBorderOpacity: "65",
  },
  night: {
    bg: "#141422",
    text: "#d4d4d8",
    textMuted: "#71717a",
    border: "#27273a",
    surface: "#1e1e32",
    heading: "#e4e4e7",
    speaker: "#a78bfa",
    bluebox: { border: "#22d3ee", bg: "rgba(6,182,212,0.08)", text: "#67e8f9", corner: "#06b6d4" },
    sceneBreak: "#3f3f5c",
    selectBg: "rgba(99,102,241,0.25)",
    annotationBgOpacity: "25",
    annotationBorderOpacity: "80",
  },
} as const

export function useReaderSettings() {
  const [settings, setSettings] = useState<ReaderSettings>(DEFAULTS)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) {
        const parsed = JSON.parse(raw)
        setSettings({ ...DEFAULTS, ...parsed })
      }
    } catch {
      // ignore
    }
    setLoaded(true)
  }, [])

  const update = useCallback(
    (patch: Partial<ReaderSettings>) => {
      setSettings((prev) => {
        const next = { ...prev, ...patch }
        try {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
        } catch {
          // ignore
        }
        return next
      })
    },
    [],
  )

  const increaseFontSize = useCallback(() => {
    setSettings((prev) => {
      const idx = FONT_SIZES.indexOf(prev.fontSize as typeof FONT_SIZES[number])
      if (idx < FONT_SIZES.length - 1) {
        const next = { ...prev, fontSize: FONT_SIZES[idx + 1] }
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
        return next
      }
      return prev
    })
  }, [])

  const decreaseFontSize = useCallback(() => {
    setSettings((prev) => {
      const idx = FONT_SIZES.indexOf(prev.fontSize as typeof FONT_SIZES[number])
      if (idx > 0) {
        const next = { ...prev, fontSize: FONT_SIZES[idx - 1] }
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
        return next
      }
      return prev
    })
  }, [])

  const cycleLineHeight = useCallback(() => {
    setSettings((prev) => {
      const idx = LINE_HEIGHTS.indexOf(prev.lineHeight as typeof LINE_HEIGHTS[number])
      const next = { ...prev, lineHeight: LINE_HEIGHTS[(idx + 1) % LINE_HEIGHTS.length] }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      return next
    })
  }, [])

  const theme = THEME_STYLES[settings.theme]

  return { settings, update, theme, loaded, increaseFontSize, decreaseFontSize, cycleLineHeight }
}
