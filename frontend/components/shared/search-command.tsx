"use client"

import { useEffect, useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import {
  Users,
  Sparkles,
  Shield,
  Crown,
  Swords,
  MapPin,
  Gem,
  Bug,
  Flag,
  Lightbulb,
  Search,
} from "lucide-react"
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import { useUIStore } from "@/stores/ui-store"
import { useBookStore } from "@/stores/book-store"
import { searchEntities } from "@/lib/api/graph"
import type { GraphNode } from "@/lib/api/types"
import { labelColor } from "@/lib/utils"

const ENTITY_ICONS: Record<string, React.ElementType> = {
  Character: Users,
  Skill: Sparkles,
  Class: Shield,
  Title: Crown,
  Event: Swords,
  Location: MapPin,
  Item: Gem,
  Creature: Bug,
  Faction: Flag,
  Concept: Lightbulb,
}

export function SearchCommand() {
  const router = useRouter()
  const { commandOpen, setCommandOpen, toggleCommandOpen } = useUIStore()
  const { selectedBookId } = useBookStore()
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<GraphNode[]>([])
  const [searching, setSearching] = useState(false)

  // Keyboard shortcut
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        toggleCommandOpen()
      }
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [toggleCommandOpen])

  const doSearch = useCallback(async (q: string) => {
    if (q.length < 2) {
      setResults([])
      return
    }
    setSearching(true)
    try {
      const res = await searchEntities(q, undefined, selectedBookId ?? undefined)
      setResults(res.slice(0, 20))
    } catch {
      setResults([])
    } finally {
      setSearching(false)
    }
  }, [selectedBookId])

  useEffect(() => {
    const timer = setTimeout(() => doSearch(query), 300)
    return () => clearTimeout(timer)
  }, [query, doSearch])

  function handleSelect(node: GraphNode) {
    const type = node.labels?.[0] ?? "Character"
    router.push(`/entity/${encodeURIComponent(type)}/${encodeURIComponent(node.name)}`)
    setCommandOpen(false)
    setQuery("")
    setResults([])
  }

  return (
    <CommandDialog open={commandOpen} onOpenChange={setCommandOpen}>
      <CommandInput
        placeholder="Search entities..."
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        <CommandEmpty>
          {searching ? "Searching..." : query.length < 2 ? "Type to search..." : "No results found."}
        </CommandEmpty>
        {results.length > 0 && (
          <CommandGroup heading="Entities">
            {results.map((node) => {
              const type = node.labels?.[0] ?? "Character"
              const Icon = ENTITY_ICONS[type] ?? Search
              return (
                <CommandItem
                  key={node.id}
                  onSelect={() => handleSelect(node)}
                  className="flex items-center gap-2"
                >
                  <span
                    className="flex h-5 w-5 items-center justify-center rounded"
                    style={{ color: labelColor(type) }}
                  >
                    <Icon className="h-3.5 w-3.5" />
                  </span>
                  <span>{node.name}</span>
                  <span className="ml-auto text-[10px] text-slate-500">{type}</span>
                </CommandItem>
              )
            })}
          </CommandGroup>
        )}
      </CommandList>
    </CommandDialog>
  )
}
