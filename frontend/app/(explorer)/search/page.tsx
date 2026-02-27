"use client"

import { useState, useEffect, useCallback } from "react"
import { Search, Filter } from "lucide-react"
import { searchEntities, listBooks } from "@/lib/api"
import type { GraphNode, BookInfo } from "@/lib/api"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { ScrollArea } from "@/components/ui/scroll-area"
import { EntityBadge } from "@/components/shared/entity-badge"
import { LABEL_COLORS } from "@/lib/utils"

const ENTITY_TYPES = Object.keys(LABEL_COLORS)

export default function SearchPage() {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<GraphNode[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [typeFilter, setTypeFilter] = useState<string | undefined>()
  const [bookFilter, setBookFilter] = useState<string | undefined>()
  const [books, setBooks] = useState<BookInfo[]>([])

  useEffect(() => {
    listBooks().then(setBooks).catch(() => {})
  }, [])

  const doSearch = useCallback(async () => {
    if (!query.trim()) return
    setLoading(true)
    setSearched(true)
    try {
      const data = await searchEntities(query.trim(), typeFilter, bookFilter)
      setResults(data)
    } catch {
      setResults([])
    } finally {
      setLoading(false)
    }
  }, [query, typeFilter, bookFilter])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    doSearch()
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Search className="h-6 w-6 text-indigo-400" />
        <h1 className="text-2xl font-bold tracking-tight">Search</h1>
      </div>

      {/* Search form */}
      <form onSubmit={handleSubmit} className="flex gap-3">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search entities by name..."
          className="flex-1"
          autoFocus
        />
        <Button type="submit" disabled={!query.trim() || loading}>
          <Search className="h-4 w-4" />
        </Button>
      </form>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5">
          <Filter className="h-3.5 w-3.5 text-slate-500" />
          <span className="text-xs text-slate-500">Type:</span>
          <Button
            variant={!typeFilter ? "secondary" : "outline"}
            size="sm"
            className="h-7 text-xs"
            onClick={() => setTypeFilter(undefined)}
          >
            All
          </Button>
          {ENTITY_TYPES.map((t) => (
            <Button
              key={t}
              variant={typeFilter === t ? "secondary" : "outline"}
              size="sm"
              className="h-7 text-xs"
              onClick={() => setTypeFilter(t)}
            >
              {t}
            </Button>
          ))}
        </div>

        {books.length > 1 && (
          <select
            aria-label="Filter by book"
            value={bookFilter ?? ""}
            onChange={(e) => setBookFilter(e.target.value || undefined)}
            className="rounded-lg border border-slate-700 bg-slate-800 px-2 py-1 text-xs focus:border-indigo-500 focus:outline-none"
          >
            <option value="">All books</option>
            {books.map((b) => (
              <option key={b.id} value={b.id}>{b.title}</option>
            ))}
          </select>
        )}
      </div>

      {/* Results */}
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      ) : searched ? (
        results.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/30 p-12 text-center">
            <p className="text-slate-500">No entities found for &ldquo;{query}&rdquo;</p>
          </div>
        ) : (
          <ScrollArea className="h-[calc(100vh-18rem)]">
            <div className="space-y-2">
              {results.map((entity) => {
                const label = entity.labels?.[0] ?? "Concept"
                return (
                  <div
                    key={entity.id}
                    className="flex items-center gap-3 rounded-lg bg-slate-900/50 border border-slate-800 px-4 py-3 hover:border-slate-700 transition-colors"
                  >
                    <EntityBadge
                      name={entity.name}
                      type={label}
                      size="md"
                    />
                    {entity.description && (
                      <p className="text-xs text-slate-500 line-clamp-1 flex-1 min-w-0">
                        {entity.description}
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
          </ScrollArea>
        )
      ) : (
        <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/30 p-12 text-center">
          <p className="text-slate-500">Enter a search term to find entities across the Knowledge Graph</p>
        </div>
      )}
    </div>
  )
}
