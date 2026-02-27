"use client"

import { Search } from "lucide-react"
import { BookSelector } from "./book-selector"
import { SearchCommand } from "./search-command"
import { useUIStore } from "@/stores/ui-store"
import { Button } from "@/components/ui/button"

export function TopBar() {
  const { setCommandOpen } = useUIStore()

  return (
    <>
      <div className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-slate-800 bg-slate-950/80 backdrop-blur-xl px-6">
        <BookSelector />

        <Button
          variant="outline"
          size="sm"
          className="gap-2 text-slate-500 border-slate-800"
          onClick={() => setCommandOpen(true)}
        >
          <Search className="h-3.5 w-3.5" />
          <span className="hidden sm:inline text-xs">Search...</span>
          <kbd className="hidden sm:inline text-[10px] font-mono bg-slate-800 px-1.5 py-0.5 rounded">
            Ctrl+K
          </kbd>
        </Button>
      </div>

      <SearchCommand />
    </>
  )
}
