"use client"

import { useState, useRef, useCallback, useEffect } from "react"
import { Search, X } from "lucide-react"
import { Input } from "@/components/ui/input"
import { getEntityHex } from "@/lib/constants"
import { searchEntities } from "@/lib/api/graph"
import type { GraphNode } from "@/lib/api/types"

interface GraphSearchProps {
  bookId?: string
  onSelect: (nodeId: string) => void
}

export function GraphSearch({ bookId, onSelect }: GraphSearchProps) {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<GraphNode[]>([])
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const doSearch = useCallback(
    (q: string) => {
      if (q.trim().length < 2) {
        setResults([])
        setOpen(false)
        return
      }
      searchEntities(q, undefined, bookId)
        .then((nodes) => {
          setResults(nodes.slice(0, 10))
          setOpen(nodes.length > 0)
          setActiveIndex(-1)
        })
        .catch(() => {
          setResults([])
          setOpen(false)
        })
    },
    [bookId],
  )

  const handleChange = useCallback(
    (value: string) => {
      setQuery(value)
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => doSearch(value), 200)
    },
    [doSearch],
  )

  const handleSelect = useCallback(
    (nodeId: string) => {
      setOpen(false)
      setQuery("")
      setResults([])
      onSelect(nodeId)
    },
    [onSelect],
  )

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false)
        return
      }
      if (!open || results.length === 0) return

      if (e.key === "ArrowDown") {
        e.preventDefault()
        setActiveIndex((prev) => (prev + 1) % results.length)
      } else if (e.key === "ArrowUp") {
        e.preventDefault()
        setActiveIndex((prev) => (prev <= 0 ? results.length - 1 : prev - 1))
      } else if (e.key === "Enter" && activeIndex >= 0) {
        e.preventDefault()
        handleSelect(results[activeIndex].id)
      }
    },
    [open, results, activeIndex, handleSelect],
  )

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  return (
    <div ref={containerRef} className="relative w-72">
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search entities..."
          value={query}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={handleKeyDown}
          className="pl-8 pr-8 h-9 bg-background/80 backdrop-blur-sm border-border/50"
        />
        {query && (
          <button
            onClick={() => {
              setQuery("")
              setResults([])
              setOpen(false)
            }}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {open && results.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 rounded-md border border-border/50 bg-popover/95 backdrop-blur-sm shadow-lg z-50 overflow-hidden">
          {results.map((node, i) => {
            const label = node.labels?.[0] ?? "Concept"
            return (
              <button
                key={node.id}
                onClick={() => handleSelect(node.id)}
                className={`flex items-center gap-2.5 w-full px-3 py-2 text-left text-sm transition-colors ${
                  i === activeIndex
                    ? "bg-accent text-accent-foreground"
                    : "hover:bg-accent/50"
                }`}
              >
                <span
                  className="h-2.5 w-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: getEntityHex(label) }}
                />
                <span className="truncate flex-1 text-foreground">{node.name}</span>
                <span className="text-xs text-muted-foreground shrink-0">{label}</span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
