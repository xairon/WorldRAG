"use client"

import Link from "next/link"
import { ArrowLeft } from "lucide-react"
import { cn } from "@/lib/utils"
import { SidebarProjectNav } from "./sidebar-project-nav"
import { SidebarBookList } from "./sidebar-book-list"
import { useEffect, useState } from "react"

interface AppSidebarProps {
  slug: string
  projectName: string
  books: { id: string; title: string; status: string; cover_image?: string | null }[]
}

export function AppSidebar({ slug, projectName, books }: AppSidebarProps) {
  const [collapsed, setCollapsed] = useState(false)

  useEffect(() => {
    const mq = window.matchMedia("(max-width: 1279px)")
    const handler = (e: MediaQueryListEvent | MediaQueryList) => setCollapsed(e.matches)
    handler(mq)
    mq.addEventListener("change", handler)
    return () => mq.removeEventListener("change", handler)
  }, [])

  return (
    <aside
      className={cn(
        "hidden md:flex flex-col border-r bg-background h-screen sticky top-0 overflow-y-auto transition-[width] duration-200",
        collapsed ? "w-14" : "w-[260px]",
      )}
      onMouseEnter={() => collapsed && setCollapsed(false)}
      onMouseLeave={() => {
        const mq = window.matchMedia("(max-width: 1279px)")
        if (mq.matches) setCollapsed(true)
      }}
    >
      {/* Project header */}
      <div className={cn("flex items-center gap-2 px-3 py-3 border-b", collapsed && "justify-center px-2")}>
        <Link href="/" className="text-muted-foreground hover:text-foreground transition-colors" title="All projects">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        {!collapsed && (
          <span className="text-sm font-display font-semibold truncate">{projectName}</span>
        )}
      </div>

      {/* Library link + Books list */}
      <div className="py-2 flex-1 overflow-y-auto">
        <SidebarBookList slug={slug} books={books} collapsed={collapsed} />
      </div>

      {/* Separator */}
      <div className="border-t mx-3" />

      {/* Tools section */}
      <div className="py-2">
        <SidebarProjectNav slug={slug} collapsed={collapsed} />
      </div>
    </aside>
  )
}
