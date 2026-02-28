"use client"

import { useRouter } from "next/navigation"
import Link from "next/link"
import {
  ChevronLeft,
  ChevronRight,
  Eye,
  EyeOff,
  Minus,
  Plus,
  Type,
  Sun,
  Moon,
  Sunset,
  AlignJustify,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { cn, LABEL_COLORS } from "@/lib/utils"
import type { ChapterInfo } from "@/lib/api/types"
import type { ReaderTheme, ReaderFont, ReaderSettings } from "@/hooks/use-reader-settings"
import { THEME_STYLES } from "@/hooks/use-reader-settings"

interface ReaderToolbarProps {
  bookId: string
  currentChapter: number
  chapters: ChapterInfo[]
  settings: ReaderSettings
  onUpdate: (patch: Partial<ReaderSettings>) => void
  onIncreaseFontSize: () => void
  onDecreaseFontSize: () => void
  onCycleLineHeight: () => void
  enabledTypes: Set<string>
  onToggleType: (type: string) => void
  typeCounts: Record<string, number>
}

export function ReaderToolbar({
  bookId,
  currentChapter,
  chapters,
  settings,
  onUpdate,
  onIncreaseFontSize,
  onDecreaseFontSize,
  onCycleLineHeight,
  enabledTypes,
  onToggleType,
  typeCounts,
}: ReaderToolbarProps) {
  const router = useRouter()
  const t = THEME_STYLES[settings.theme]

  const prevChapter = chapters
    .filter((c) => c.number < currentChapter)
    .sort((a, b) => b.number - a.number)[0]
  const nextChapter = chapters
    .filter((c) => c.number > currentChapter)
    .sort((a, b) => a.number - b.number)[0]

  const currentChapterInfo = chapters.find((c) => c.number === currentChapter)

  const themeIcons: Record<ReaderTheme, React.ReactNode> = {
    white: <Sun className="h-3.5 w-3.5" />,
    sepia: <Sunset className="h-3.5 w-3.5" />,
    night: <Moon className="h-3.5 w-3.5" />,
  }

  return (
    <div
      className="sticky top-0 z-30 backdrop-blur-md border-b"
      style={{
        backgroundColor: `${t.bg}ee`,
        borderColor: t.border,
      }}
    >
      <div className="max-w-[780px] mx-auto flex items-center justify-between px-4 h-11">
        {/* Left: Navigation */}
        <div className="flex items-center gap-1">
          {prevChapter ? (
            <Link href={`/read/${bookId}/${prevChapter.number}`}>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                style={{ color: t.textMuted }}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
            </Link>
          ) : (
            <div className="w-7" />
          )}

          <select
            aria-label="Select chapter"
            value={currentChapter}
            onChange={(e) => router.push(`/read/${bookId}/${e.target.value}`)}
            className="text-xs font-medium border-0 bg-transparent focus:outline-none cursor-pointer max-w-[180px] truncate"
            style={{ color: t.text }}
          >
            {chapters.map((ch) => (
              <option key={ch.number} value={ch.number}>
                Ch. {ch.number} {ch.title ? `\u2014 ${ch.title}` : ""}
              </option>
            ))}
          </select>

          {nextChapter ? (
            <Link href={`/read/${bookId}/${nextChapter.number}`}>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                style={{ color: t.textMuted }}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </Link>
          ) : (
            <div className="w-7" />
          )}
        </div>

        {/* Right: Controls */}
        <div className="flex items-center gap-0.5">
          {/* Annotations toggle */}
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            style={{ color: settings.annotations ? "#6366f1" : t.textMuted }}
            onClick={() => onUpdate({ annotations: !settings.annotations })}
            title={settings.annotations ? "Hide annotations" : "Show annotations"}
          >
            {settings.annotations ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
          </Button>

          {/* Annotation type filters */}
          {settings.annotations && (
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 text-[10px] px-2"
                  style={{ color: t.textMuted }}
                >
                  Filters
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-56 p-3" align="end">
                <p className="text-xs font-medium mb-2 text-slate-400">Entity types</p>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(LABEL_COLORS).map(([label, color]) => {
                    const count = typeCounts[label] ?? 0
                    if (count === 0) return null
                    const active = enabledTypes.has(label)
                    return (
                      <button
                        key={label}
                        onClick={() => onToggleType(label)}
                        className={cn(
                          "inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium transition-all",
                          active ? "opacity-100" : "opacity-40 hover:opacity-70",
                        )}
                        style={{
                          backgroundColor: active ? `${color}20` : "transparent",
                          border: `1px solid ${active ? color + "40" : "transparent"}`,
                          color: active ? color : undefined,
                        }}
                      >
                        <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
                        {label}
                        <span className="opacity-60">{count}</span>
                      </button>
                    )
                  })}
                </div>
              </PopoverContent>
            </Popover>
          )}

          {/* Typography settings */}
          <Popover>
            <PopoverTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                style={{ color: t.textMuted }}
                title="Typography settings"
              >
                <Type className="h-3.5 w-3.5" />
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-52 p-3 space-y-4" align="end">
              {/* Font size */}
              <div>
                <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-2">Size</p>
                <div className="flex items-center justify-between">
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-7 w-7"
                    onClick={onDecreaseFontSize}
                    disabled={settings.fontSize <= 14}
                  >
                    <Minus className="h-3 w-3" />
                  </Button>
                  <span className="text-sm tabular-nums">{settings.fontSize}px</span>
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-7 w-7"
                    onClick={onIncreaseFontSize}
                    disabled={settings.fontSize >= 22}
                  >
                    <Plus className="h-3 w-3" />
                  </Button>
                </div>
              </div>

              {/* Font family */}
              <div>
                <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-2">Font</p>
                <div className="flex gap-1.5">
                  {(["serif", "sans"] as const).map((f) => (
                    <button
                      key={f}
                      onClick={() => onUpdate({ fontFamily: f })}
                      className={cn(
                        "flex-1 py-1.5 rounded-md text-xs transition-colors",
                        settings.fontFamily === f
                          ? "bg-indigo-500/20 text-indigo-400 border border-indigo-500/30"
                          : "bg-slate-800 text-slate-400 border border-transparent hover:bg-slate-700",
                      )}
                      style={{
                        fontFamily:
                          f === "serif"
                            ? '"Literata", Georgia, serif'
                            : '"Inter", system-ui, sans-serif',
                      }}
                    >
                      {f === "serif" ? "Serif" : "Sans"}
                    </button>
                  ))}
                </div>
              </div>

              {/* Line height */}
              <div>
                <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-2">Spacing</p>
                <button
                  onClick={onCycleLineHeight}
                  className="flex items-center gap-2 w-full py-1.5 px-2 rounded-md bg-slate-800 text-slate-400 text-xs hover:bg-slate-700 transition-colors"
                >
                  <AlignJustify className="h-3 w-3" />
                  <span>{settings.lineHeight.toFixed(1)}x</span>
                </button>
              </div>
            </PopoverContent>
          </Popover>

          {/* Theme switcher */}
          <Popover>
            <PopoverTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                style={{ color: t.textMuted }}
                title="Reading theme"
              >
                {themeIcons[settings.theme]}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-44 p-2" align="end">
              {(["white", "sepia", "night"] as const).map((th) => {
                const ts = THEME_STYLES[th]
                const labels: Record<ReaderTheme, string> = {
                  white: "Light",
                  sepia: "Sepia",
                  night: "Night",
                }
                return (
                  <button
                    key={th}
                    onClick={() => onUpdate({ theme: th })}
                    className={cn(
                      "flex items-center gap-3 w-full px-3 py-2 rounded-md text-xs transition-colors",
                      settings.theme === th
                        ? "bg-indigo-500/15 text-indigo-400"
                        : "text-slate-400 hover:bg-slate-800",
                    )}
                  >
                    <span
                      className="h-5 w-5 rounded-full border"
                      style={{
                        backgroundColor: ts.bg,
                        borderColor: ts.border,
                      }}
                    />
                    {labels[th]}
                    {themeIcons[th]}
                  </button>
                )
              })}
            </PopoverContent>
          </Popover>
        </div>
      </div>
    </div>
  )
}
