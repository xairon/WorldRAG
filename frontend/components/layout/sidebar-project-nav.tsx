"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Network, MessageCircle, Dna, Settings } from "lucide-react"
import { cn } from "@/lib/utils"

const NAV_ITEMS = [
  { href: "graph", label: "Graph", icon: Network },
  { href: "chat", label: "Chat", icon: MessageCircle },
  { href: "profile", label: "Profile", icon: Dna },
  { href: "settings", label: "Settings", icon: Settings },
] as const

export function SidebarProjectNav({
  slug,
  collapsed,
}: {
  slug: string
  collapsed: boolean
}) {
  const pathname = usePathname()

  return (
    <nav className="flex flex-col gap-0.5 px-2">
      {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
        const fullHref = `/projects/${slug}/${href}`
        const isActive = pathname.startsWith(fullHref)
        return (
          <Link
            key={href}
            href={fullHref}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
              "hover:bg-muted/50",
              isActive && "bg-muted font-medium",
              collapsed && "justify-center px-2",
            )}
            title={collapsed ? label : undefined}
          >
            <Icon className="h-4 w-4 shrink-0" />
            {!collapsed && <span>{label}</span>}
          </Link>
        )
      })}
    </nav>
  )
}
