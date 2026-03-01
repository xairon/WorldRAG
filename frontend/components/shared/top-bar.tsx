"use client"

import { Search } from "lucide-react"
import { BookSelector } from "./book-selector"
import { SearchCommand } from "./search-command"
import { ThemeToggle } from "./theme-toggle"
import { useUIStore } from "@/stores/ui-store"
import { Button } from "@/components/ui/button"

export function TopBar() {
  const { setCommandOpen } = useUIStore()

  return (
    <>
      <div className="glass sticky top-0 z-30 flex h-14 items-center justify-between px-6">
        <BookSelector />

        <div className="flex items-center gap-2">
          <ThemeToggle />

          <Button
            variant="outline"
            size="sm"
            className="gap-2 text-muted-foreground"
            onClick={() => setCommandOpen(true)}
          >
            <Search className="h-3.5 w-3.5" />
            <span className="hidden text-xs sm:inline">Search...</span>
            <kbd className="hidden rounded bg-accent px-1.5 py-0.5 font-mono text-[10px] sm:inline">
              Ctrl+K
            </kbd>
          </Button>
        </div>
      </div>

      <SearchCommand />
    </>
  )
}
