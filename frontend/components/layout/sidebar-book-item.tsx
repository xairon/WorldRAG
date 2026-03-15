"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { ChevronRight, BookOpen, FileText, Pickaxe } from "lucide-react"
import { cn } from "@/lib/utils"
import { StatusBadge } from "@/components/shared/status-badge"
import { mapBackendStatus } from "@/lib/constants"
import { useUIStore } from "@/stores/ui-store"

interface BookItemProps {
  slug: string
  bookId: string
  title: string
  status: string // backend ProcessingStatus value
  collapsed: boolean
}

const SUB_NAV = [
  { href: "chapters", label: "Chapters", icon: FileText },
  { href: "reader", label: "Reader", icon: BookOpen },
  { href: "extraction", label: "Extraction", icon: Pickaxe },
] as const

export function SidebarBookItem({ slug, bookId, title, status, collapsed }: BookItemProps) {
  const pathname = usePathname()
  const { expandedBooks, toggleBookExpanded } = useUIStore()
  const isExpanded = expandedBooks[bookId] ?? false
  const uiStatus = mapBackendStatus(status)
  const bookBase = `/projects/${slug}/books/${bookId}`
  const isActive = pathname.startsWith(bookBase)

  if (collapsed) {
    return (
      <Link
        href={`${bookBase}/chapters`}
        className={cn(
          "flex items-center justify-center rounded-md p-2 hover:bg-muted/50",
          isActive && "bg-muted",
        )}
        title={title}
      >
        <BookOpen className="h-4 w-4" />
      </Link>
    )
  }

  return (
    <div>
      <button
        onClick={() => toggleBookExpanded(bookId)}
        className={cn(
          "flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-sm hover:bg-muted/50",
          isActive && "bg-muted/50",
        )}
      >
        <ChevronRight
          className={cn("h-3 w-3 shrink-0 transition-transform", isExpanded && "rotate-90")}
        />
        <span className="truncate flex-1 text-left">{title}</span>
        <StatusBadge status={uiStatus} className="ml-auto" />
      </button>

      {isExpanded && (
        <div className="ml-4 mt-0.5 flex flex-col gap-0.5 border-l pl-2">
          {SUB_NAV.map(({ href, label, icon: Icon }) => {
            const fullHref = `${bookBase}/${href}`
            const isSubActive = pathname.startsWith(fullHref)
            return (
              <Link
                key={href}
                href={fullHref}
                className={cn(
                  "flex items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors",
                  "hover:bg-muted/50 text-muted-foreground",
                  isSubActive && "text-foreground font-medium",
                )}
              >
                <Icon className="h-3 w-3" />
                <span>{label}</span>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
