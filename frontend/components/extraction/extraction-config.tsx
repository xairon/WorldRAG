"use client"

import { useState } from "react"
import { Settings2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Input } from "@/components/ui/input"

export interface ExtractionConfig {
  language: string
  genre: string
  series_name: string
  provider?: string
}

interface ExtractionConfigPanelProps {
  bookGenre: string
  bookSeriesName: string | null
  bookTitle: string
  onStart: (config: ExtractionConfig) => void
  disabled?: boolean
}

const LANGUAGES = [
  { value: "fr", label: "Français" },
  { value: "en", label: "English" },
] as const

const GENRES = [
  { value: "litrpg", label: "LitRPG / Progression Fantasy" },
  { value: "fantasy", label: "Fantasy classique" },
  { value: "core", label: "Générique (core only)" },
] as const

const MODELS = [
  { value: "", label: "Default (DeepSeek V3.2)" },
  { value: "openrouter:deepseek/deepseek-v3.2", label: "DeepSeek V3.2 — $0.26/M in" },
  { value: "openrouter:deepseek/deepseek-r1", label: "DeepSeek R1 — $0.55/M in (reasoning)" },
  { value: "openrouter:google/gemini-2.5-flash", label: "Gemini 2.5 Flash — $0.15/M in" },
  { value: "openrouter:google/gemini-2.5-pro", label: "Gemini 2.5 Pro — $1.25/M in" },
  { value: "openrouter:anthropic/claude-sonnet-4", label: "Claude Sonnet 4 — $3/M in" },
  { value: "openrouter:qwen/qwen3-235b-a22b", label: "Qwen3 235B — $0.20/M in" },
  { value: "openrouter:meta-llama/llama-4-maverick", label: "Llama 4 Maverick — $0.20/M in" },
] as const

function detectLanguage(title: string): string {
  const frPatterns = /version française|édition française|tome|chapitre|aventure/i
  return frPatterns.test(title) ? "fr" : "en"
}

export function ExtractionConfigPanel({
  bookGenre,
  bookSeriesName,
  bookTitle,
  onStart,
  disabled = false,
}: ExtractionConfigPanelProps) {
  const detectedLang = detectLanguage(bookTitle)
  const [language, setLanguage] = useState(detectedLang)
  const [genre, setGenre] = useState(bookGenre || "litrpg")
  const [seriesName, setSeriesName] = useState(bookSeriesName || "")
  const [provider, setProvider] = useState("")
  const [showAdvanced, setShowAdvanced] = useState(false)

  const handleStart = () => {
    onStart({
      language,
      genre,
      series_name: seriesName,
      provider: provider || undefined,
    })
  }

  return (
    <div className="rounded-lg border bg-card p-4 space-y-4">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Settings2 className="h-4 w-4" />
        Extraction configuration
      </div>

      {/* Primary settings */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="space-y-2">
          <Label htmlFor="language">Language</Label>
          <Select value={language} onValueChange={setLanguage}>
            <SelectTrigger id="language">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {LANGUAGES.map((l) => (
                <SelectItem key={l.value} value={l.value}>
                  {l.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {detectedLang === "fr" && language === "fr" && (
            <p className="text-xs text-muted-foreground">
              Auto-detected from title
            </p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="genre">Genre</Label>
          <Select value={genre} onValueChange={setGenre}>
            <SelectTrigger id="genre">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {GENRES.map((g) => (
                <SelectItem key={g.value} value={g.value}>
                  {g.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="series">Series</Label>
          <Input
            id="series"
            value={seriesName}
            onChange={(e) => setSeriesName(e.target.value)}
            placeholder="e.g. primal_hunter"
          />
        </div>
      </div>

      {/* Advanced settings */}
      <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
        <CollapsibleTrigger className="text-xs text-muted-foreground hover:text-foreground transition-colors">
          {showAdvanced ? "▼" : "▶"} Advanced settings
        </CollapsibleTrigger>
        <CollapsibleContent className="pt-3">
          <div className="space-y-2">
            <Label htmlFor="model">LLM Model (via OpenRouter)</Label>
            <Select value={provider} onValueChange={setProvider}>
              <SelectTrigger id="model">
                <SelectValue placeholder="Default (DeepSeek V3.2)" />
              </SelectTrigger>
              <SelectContent>
                {MODELS.map((m) => (
                  <SelectItem key={m.value} value={m.value}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CollapsibleContent>
      </Collapsible>

      {/* Start button */}
      <Button onClick={handleStart} disabled={disabled} className="w-full">
        Start extraction
      </Button>
    </div>
  )
}
