"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { BookOpen } from "lucide-react"
import { cn } from "@/lib/utils"
import { SidebarBookItem } from "./sidebar-book-item"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { useState } from "react"

interface SidebarBookListProps {
  slug: string
  books: { id: string; title: string; status: string; cover_image?: string | null }[]
  collapsed: boolean
}

export function SidebarBookList({ slug, books, collapsed }: SidebarBookListProps) {
  const pathname = usePathname()
  const isLibraryActive = pathname === `/projects/${slug}`
  const [showAll, setShowAll] = useState(false)
  const visibleBooks = showAll ? books : books.slice(0, 5)
  const hasMore = books.length > 5

  const libraryLink = (
    <Link
      href={`/projects/${slug}`}
      className={cn(
        "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
        collapsed && "justify-center px-2",
        isLibraryActive
          ? "bg-primary/10 text-primary font-medium"
          : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
      )}
    >
      <BookOpen className="h-4 w-4 shrink-0" />
      {!collapsed && (
        <>
          <span className="flex-1">Library</span>
          <span className="text-xs text-muted-foreground font-mono">{books.length}</span>
        </>
      )}
    </Link>
  )

  return (
    <div className="space-y-0.5">
      {collapsed ? (
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger asChild>{libraryLink}</TooltipTrigger>
            <TooltipContent side="right">Library ({books.length})</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      ) : (
        libraryLink
      )}

      {!collapsed && books.length > 0 && (
        <div className="ml-4 border-l pl-2 space-y-0.5">
          {visibleBooks.map((book) => (
            <SidebarBookItem key={book.id} slug={slug} book={book} />
          ))}
          {hasMore && !showAll && (
            <button
              onClick={() => setShowAll(true)}
              className="text-xs text-muted-foreground hover:text-foreground px-2 py-1 transition-colors"
            >
              Show {books.length - 5} more...
            </button>
          )}
        </div>
      )}
    </div>
  )
}
