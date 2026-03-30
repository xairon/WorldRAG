"use client"

import { useState } from "react"
import { Swords, Wand2, Rocket, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { Checkbox } from "@/components/ui/checkbox"
import { useBookDetail } from "@/hooks/use-books"
import { useTriggerExtraction } from "@/hooks/use-extraction"
import { ErrorState } from "@/components/ui/error-state"
import { cn } from "@/lib/utils"

const GENRES = [
  { key: "litrpg", label: "LitRPG", icon: Swords },
  { key: "fantasy", label: "Fantasy", icon: Wand2 },
  { key: "sci-fi", label: "Sci-Fi", icon: Rocket },
] as const

const LANGUAGES = [
  { key: "fr", label: "FR" },
  { key: "en", label: "EN" },
] as const

const PROVIDERS = [
  { key: "gemini:gemini-2.5-flash", label: "Gemini 2.5 Flash", cost: "free" },
  { key: "openrouter:deepseek/deepseek-chat-v3-0324", label: "DeepSeek V3.2", cost: "$0.26/M" },
  { key: "local:qwen3:32b", label: "Ollama (qwen3:32b)", cost: "local" },
] as const

interface ConfigureStepProps {
  projectSlug: string
  bookId: string
  onContinue: () => void
}

export function ConfigureStep({ projectSlug: _projectSlug, bookId, onContinue }: ConfigureStepProps) {
  const { data: bookDetail, isLoading, error } = useBookDetail(bookId)
  const triggerMutation = useTriggerExtraction()

  const [genre, setGenre] = useState("litrpg")
  const [language, setLanguage] = useState("fr")
  const [provider, setProvider] = useState<string>(PROVIDERS[0].key)
  const [selectedChapters, setSelectedChapters] = useState<number[]>([])
  const [showAdvanced, setShowAdvanced] = useState(false)

  if (error) return <ErrorState title="Failed to load book" error={error as Error} />

  const chapters = bookDetail?.chapters ?? []

  const handleStart = () => {
    triggerMutation.mutate(
      {
        bookId,
        genre,
        language,
        provider,
        chapters: selectedChapters.length > 0 ? selectedChapters : undefined,
      },
      { onSuccess: onContinue },
    )
  }

  const toggleChapter = (num: number) => {
    setSelectedChapters((prev) =>
      prev.includes(num) ? prev.filter((n) => n !== num) : [...prev, num],
    )
  }

  return (
    <div className="space-y-8">
      {/* Book info */}
      {bookDetail && (
        <div className="flex items-center gap-4 p-4 rounded-lg bg-muted/50">
          <div>
            <p className="font-semibold">{bookDetail.book.title}</p>
            <p className="text-xs text-muted-foreground">
              {bookDetail.book.total_chapters} chapters
              {bookDetail.book.author ? ` \u00b7 ${bookDetail.book.author}` : ""}
            </p>
          </div>
        </div>
      )}

      {/* Genre */}
      <div>
        <label className="text-sm font-medium mb-3 block">Genre</label>
        <div className="grid grid-cols-3 gap-3">
          {GENRES.map((g) => (
            <Card
              key={g.key}
              className={cn(
                "cursor-pointer transition-all hover:bg-accent/50",
                genre === g.key && "border-primary ring-1 ring-primary",
              )}
              onClick={() => setGenre(g.key)}
            >
              <CardContent className="flex flex-col items-center gap-2 p-4">
                <g.icon className="h-6 w-6" />
                <span className="text-sm font-medium">{g.label}</span>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Language */}
      <div>
        <label className="text-sm font-medium mb-3 block">Source language</label>
        <div className="flex gap-1 p-1 bg-muted rounded-lg w-fit">
          {LANGUAGES.map((l) => (
            <button
              key={l.key}
              onClick={() => setLanguage(l.key)}
              className={cn(
                "px-4 py-1.5 text-sm font-medium rounded-md transition-colors",
                language === l.key
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>

      {/* Provider */}
      <div>
        <label className="text-sm font-medium mb-3 block">LLM Provider</label>
        <Select value={provider} onValueChange={setProvider}>
          <SelectTrigger className="w-full max-w-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PROVIDERS.map((p) => (
              <SelectItem key={p.key} value={p.key}>
                <span>{p.label}</span>
                <span className="ml-2 text-xs text-muted-foreground">({p.cost})</span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Advanced: chapter selection */}
      <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
        <CollapsibleTrigger className="text-sm text-muted-foreground hover:underline">
          {showAdvanced ? "Hide" : "Show"} advanced options
        </CollapsibleTrigger>
        <CollapsibleContent className="mt-3">
          <p className="text-xs text-muted-foreground mb-2">
            Select specific chapters to extract (leave empty for all):
          </p>
          <div className="grid grid-cols-6 sm:grid-cols-8 md:grid-cols-10 gap-2 max-h-48 overflow-auto">
            {chapters.map((ch) => (
              <label
                key={ch.number}
                className="flex items-center gap-1.5 text-xs cursor-pointer"
              >
                <Checkbox
                  checked={selectedChapters.includes(ch.number)}
                  onCheckedChange={() => toggleChapter(ch.number)}
                />
                {ch.number}
              </label>
            ))}
          </div>
        </CollapsibleContent>
      </Collapsible>

      {/* CTA */}
      <Button
        size="lg"
        className="w-full"
        onClick={handleStart}
        disabled={triggerMutation.isPending || isLoading}
      >
        {triggerMutation.isPending ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Starting...
          </>
        ) : (
          "Start extraction"
        )}
      </Button>

      {triggerMutation.isError && (
        <ErrorState
          title="Failed to start extraction"
          error={triggerMutation.error as Error}
          onRetry={() => triggerMutation.reset()}
        />
      )}
    </div>
  )
}
