"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Network,
  BookOpen,
  MessageSquare,
  LayoutDashboard,
  Telescope,
  Search,
  Users,
  Menu,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useUIStore } from "@/stores/ui-store"
import { motion } from "motion/react"

const NAV_SECTIONS = [
  {
    label: "Reader",
    items: [
      { href: "/library", label: "Library", icon: BookOpen },
      { href: "/chat", label: "Chat", icon: MessageSquare },
    ],
  },
  {
    label: "Explorer",
    items: [
      { href: "/graph", label: "Graph", icon: Network },
      { href: "/search", label: "Search", icon: Search },
      { href: "/characters", label: "Characters", icon: Users },
    ],
  },
  {
    label: "Pipeline",
    items: [
      { href: "/pipeline", label: "Dashboard", icon: Telescope },
    ],
  },
]

export function Sidebar() {
  const pathname = usePathname()
  const { mobileSidebarOpen, toggleSidebar } = useUIStore()

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={toggleSidebar}
        className="glass fixed top-3 left-3 z-50 rounded-lg p-2 md:hidden"
        aria-label="Toggle sidebar"
      >
        {mobileSidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>

      {/* Mobile overlay */}
      {mobileSidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={toggleSidebar}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "glass fixed left-0 top-0 z-40 h-screen w-60 border-r border-[var(--glass-border)] transition-transform",
          "md:translate-x-0",
          mobileSidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
        )}
      >
        <div className="flex h-14 items-center gap-2 border-b border-[var(--glass-border)] px-5">
          <Network className="h-5 w-5 text-[var(--primary)]" />
          <span className="font-display text-base font-bold tracking-tight">
            World<span className="text-[var(--primary)]">RAG</span>
          </span>
        </div>

        <nav aria-label="Main navigation" className="mt-4 flex flex-col gap-6 px-3">
          {/* Dashboard */}
          <NavItem href="/" label="Dashboard" icon={LayoutDashboard} active={pathname === "/"} />

          {NAV_SECTIONS.map((section) => (
            <div key={section.label}>
              <div className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">
                {section.label}
              </div>
              <div className="flex flex-col gap-0.5">
                {section.items.map(({ href, label, icon }) => (
                  <NavItem
                    key={href}
                    href={href}
                    label={label}
                    icon={icon}
                    active={pathname.startsWith(href)}
                  />
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="absolute bottom-4 left-0 right-0 px-5">
          <div className="glass rounded-lg p-3 text-xs text-muted-foreground">
            <div className="mb-0.5 font-medium text-foreground">WorldRAG v0.2</div>
            Fiction Knowledge Graph Platform
          </div>
        </div>
      </aside>
    </>
  )
}

function NavItem({
  href,
  label,
  icon: Icon,
  active,
}: {
  href: string
  label: string
  icon: React.ElementType
  active: boolean
}) {
  return (
    <Link
      href={href}
      className={cn(
        "relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
        active
          ? "text-foreground"
          : "text-muted-foreground hover:bg-accent hover:text-foreground",
      )}
    >
      {active && (
        <motion.div
          layoutId="sidebar-active"
          className="absolute inset-0 rounded-lg bg-[var(--primary)]/10 ring-1 ring-[var(--primary)]/20"
          transition={{ type: "spring", stiffness: 350, damping: 30 }}
        />
      )}
      <Icon className="relative z-10 h-4 w-4" />
      <span className="relative z-10">{label}</span>
    </Link>
  )
}
