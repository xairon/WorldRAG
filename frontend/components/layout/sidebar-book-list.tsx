"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Library } from "lucide-react"
import { cn } from "@/lib/utils"
import { SidebarBookItem } from "./sidebar-book-item"

interface Book {
  id: string
  title: string
  status: string
}

export function SidebarBookList({
  slug,
  books,
  collapsed,
}: {
  slug: string
  books: Book[]
  collapsed: boolean
}) {
  const pathname = usePathname()
  const booksActive = pathname === `/projects/${slug}`

  return (
    <div className="flex flex-col gap-1">
      {/* Books header */}
      <Link
        href={`/projects/${slug}`}
        className={cn(
          "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors hover:bg-muted/50",
          booksActive && "bg-muted font-medium",
          collapsed && "justify-center px-2",
        )}
        title={collapsed ? "Books" : undefined}
      >
        <Library className="h-4 w-4 shrink-0" />
        {!collapsed && <span>Books</span>}
        {!collapsed && (
          <span className="ml-auto text-xs text-muted-foreground font-mono">{books.length}</span>
        )}
      </Link>

      {/* Book items */}
      {!collapsed && (
        <div className="flex flex-col gap-0.5 px-1">
          {books.map((book) => (
            <SidebarBookItem
              key={book.id}
              slug={slug}
              bookId={book.id}
              title={book.title}
              status={book.status}
              collapsed={collapsed}
            />
          ))}
        </div>
      )}
    </div>
  )
}
