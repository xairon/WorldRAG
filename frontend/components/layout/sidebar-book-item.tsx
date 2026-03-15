"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"

const statusColors: Record<string, string> = {
  pending: "bg-muted-foreground",
  parsing: "bg-amber-500",
  ready: "bg-blue-500",
  extracting: "bg-violet-500",
  extracted: "bg-emerald-500",
  embedding: "bg-cyan-500",
  embedded: "bg-emerald-500",
  done: "bg-emerald-500",
  error: "bg-red-500",
}

interface SidebarBookItemProps {
  slug: string
  book: { id: string; title: string; status: string; cover_image?: string | null }
}

export function SidebarBookItem({ slug, book }: SidebarBookItemProps) {
  const pathname = usePathname()
  const href = `/projects/${slug}/books/${book.id}`
  const isActive = pathname.startsWith(href)
  const dotColor = statusColors[book.status] ?? "bg-muted-foreground"

  return (
    <Link
      href={href}
      className={cn(
        "flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors",
        isActive
          ? "bg-primary/10 text-primary font-medium"
          : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
      )}
    >
      {book.cover_image ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={book.cover_image} alt="" className="w-7 h-10 rounded-sm object-cover shrink-0" />
      ) : (
        <div className="w-7 h-10 rounded-sm bg-muted shrink-0 flex items-center justify-center">
          <span className="text-[10px] font-mono text-muted-foreground">
            {book.title.charAt(0).toUpperCase()}
          </span>
        </div>
      )}
      <span className="truncate flex-1">{book.title}</span>
      <span className={cn("h-2 w-2 rounded-full shrink-0", dotColor)} title={book.status} />
    </Link>
  )
}
