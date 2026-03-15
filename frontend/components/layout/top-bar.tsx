"use client"

import { ThemeToggle } from "@/components/shared/theme-toggle"
import { MobileDrawer } from "./mobile-drawer"

interface TopBarProps {
  breadcrumbs?: { label: string; href?: string }[]
  drawer?: {
    slug: string
    projectName: string
    books: { id: string; title: string; status: string }[]
  }
}

export function TopBar({ breadcrumbs, drawer }: TopBarProps) {
  return (
    <header className="sticky top-0 z-30 flex h-12 items-center gap-3 border-b bg-background px-4">
      {drawer && <MobileDrawer {...drawer} />}
      <nav className="flex items-center gap-1.5 text-sm min-w-0 flex-1">
        {breadcrumbs?.map((crumb, i) => (
          <span key={i} className="flex items-center gap-1.5 min-w-0">
            {i > 0 && <span className="text-muted-foreground">&rsaquo;</span>}
            {crumb.href ? (
              <a href={crumb.href} className="text-muted-foreground hover:text-foreground truncate">{crumb.label}</a>
            ) : (
              <span className="truncate font-medium">{crumb.label}</span>
            )}
          </span>
        ))}
      </nav>
      <ThemeToggle />
    </header>
  )
}
