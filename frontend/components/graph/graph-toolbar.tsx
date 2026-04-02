"use client"

import { useState, useEffect, useRef } from "react"
import { Search, X, Plus, Minus, Maximize2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useGraphSearch } from "@/hooks/use-graph"
import { getEntityHex } from "@/lib/constants"
import { cn } from "@/lib/utils"

interface GraphToolbarProps {
  // Book selector
  books: Array<{ id: string; title: string }>
  selectedBookId: string
  onBookChange: (bookId: string) => void
  // Label filters
  availableLabels: string[]
  activeLabels: string[]
  onLabelsChange: (labels: string[]) => void
  // Chapter filter
  maxChapter: number
  chapterFilter: number | null
  onChapterChange: (chapter: number | null) => void
  // Search
  bookId: string
  onSearchSelect: (nodeId: string) => void
  // Stats
  nodeCount: number
  edgeCount: number
  // Zoom
  onZoomIn: () => void
  onZoomOut: () => void
  onFit: () => void
}

export function GraphToolbar({
  books,
  selectedBookId,
  onBookChange,
  availableLabels,
  activeLabels,
  onLabelsChange,
  maxChapter,
  chapterFilter,
  onChapterChange,
  bookId,
  onSearchSelect,
  nodeCount,
  edgeCount,
  onZoomIn,
  onZoomOut,
  onFit,
}: GraphToolbarProps) {
  // Search state
  const [searchQuery, setSearchQuery] = useState("")
  const [debouncedQuery, setDebouncedQuery] = useState("")
  const [searchOpen, setSearchOpen] = useState(false)
  const [activeIdx, setActiveIdx] = useState(0)
  const searchRef = useRef<HTMLDivElement>(null)

  const { data: searchResults } = useGraphSearch(bookId, debouncedQuery)

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(searchQuery), 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  // Open dropdown when results arrive
  useEffect(() => {
    if (searchResults && searchResults.length > 0) {
      setSearchOpen(true)
      setActiveIdx(0)
    }
  }, [searchResults])

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setSearchOpen(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (!searchResults?.length) return
    if (e.key === "ArrowDown") {
      e.preventDefault()
      setActiveIdx((i) => Math.min(i + 1, searchResults.length - 1))
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setActiveIdx((i) => Math.max(i - 1, 0))
    } else if (e.key === "Enter" && searchResults[activeIdx]) {
      e.preventDefault()
      onSearchSelect(searchResults[activeIdx].id)
      setSearchOpen(false)
      setSearchQuery("")
    } else if (e.key === "Escape") {
      setSearchOpen(false)
    }
  }

  const toggleLabel = (label: string) => {
    if (activeLabels.includes(label)) {
      onLabelsChange(activeLabels.filter((l) => l !== label))
    } else {
      onLabelsChange([...activeLabels, label])
    }
  }

  return (
    <div className="flex items-center gap-2 flex-wrap p-2 bg-background/80 backdrop-blur border-b">
      {/* Book selector */}
      {books.length > 1 && (
        <Select value={selectedBookId} onValueChange={onBookChange}>
          <SelectTrigger className="w-40 h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {books.map((b) => (
              <SelectItem key={b.id} value={b.id}>
                {b.title}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {/* Entity type badges */}
      <div className="flex gap-1 flex-wrap">
        {availableLabels.map((label) => {
          const active = activeLabels.length === 0 || activeLabels.includes(label)
          return (
            <Badge
              key={label}
              variant={active ? "default" : "outline"}
              className="cursor-pointer text-xs transition-opacity"
              style={{
                backgroundColor: active ? getEntityHex(label) : "transparent",
                borderColor: getEntityHex(label),
                color: active ? "white" : undefined,
                opacity: active ? 1 : 0.4,
              }}
              onClick={() => toggleLabel(label)}
            >
              {label}
            </Badge>
          )
        })}
      </div>

      {/* Chapter filter */}
      {maxChapter > 1 && (
        <Select
          value={chapterFilter ? String(chapterFilter) : "all"}
          onValueChange={(v) => onChapterChange(v === "all" ? null : Number(v))}
        >
          <SelectTrigger className="w-28 h-8 text-xs">
            <SelectValue placeholder="Chapter" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All chapters</SelectItem>
            {Array.from({ length: maxChapter }, (_, i) => i + 1).map((ch) => (
              <SelectItem key={ch} value={String(ch)}>
                Ch. {ch}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {/* Separator */}
      <div className="w-px h-5 bg-border mx-1" />

      {/* Search */}
      <div ref={searchRef} className="relative">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            onFocus={() => searchResults?.length && setSearchOpen(true)}
            placeholder="Search entities..."
            className="h-8 w-48 pl-8 text-xs"
          />
          {searchQuery && (
            <button
              onClick={() => {
                setSearchQuery("")
                setSearchOpen(false)
              }}
              className="absolute right-2 top-1/2 -translate-y-1/2"
            >
              <X className="h-3 w-3 text-muted-foreground" />
            </button>
          )}
        </div>

        {/* Search dropdown */}
        {searchOpen && searchResults && searchResults.length > 0 && (
          <div className="absolute top-full left-0 mt-1 w-64 max-h-60 overflow-auto bg-popover border rounded-lg shadow-lg z-50">
            {searchResults.map((result, i) => (
              <button
                key={result.id}
                className={cn(
                  "w-full text-left px-3 py-2 text-xs hover:bg-accent flex items-center gap-2",
                  i === activeIdx && "bg-accent",
                )}
                onClick={() => {
                  onSearchSelect(result.id)
                  setSearchOpen(false)
                  setSearchQuery("")
                }}
              >
                <span
                  className="h-2 w-2 rounded-full shrink-0"
                  style={{
                    backgroundColor: getEntityHex(result.labels?.[0] ?? ""),
                  }}
                />
                <span className="truncate font-medium">{result.name}</span>
                <span className="text-muted-foreground ml-auto">
                  {result.labels?.[0]}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Separator */}
      <div className="w-px h-5 bg-border mx-1" />

      {/* Stats */}
      <span className="text-xs text-muted-foreground tabular-nums">
        {nodeCount.toLocaleString()} nodes · {edgeCount.toLocaleString()} edges
      </span>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Zoom controls */}
      <div className="flex gap-1">
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={onZoomIn}
          aria-label="Zoom in"
        >
          <Plus className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={onFit}
          aria-label="Fit to screen"
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={onZoomOut}
          aria-label="Zoom out"
        >
          <Minus className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  )
}
