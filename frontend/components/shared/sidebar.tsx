"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Network,
  BookOpen,
  MessageSquare,
  LayoutDashboard,
  Telescope,
  Clock,
  Search,
  Users,
  Menu,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useUIStore } from "@/stores/ui-store"

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
  const { sidebarCollapsed, toggleSidebar } = useUIStore()

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={toggleSidebar}
        className="fixed top-3 left-3 z-50 md:hidden rounded-lg bg-slate-900 border border-slate-800 p-2"
        aria-label="Toggle sidebar"
      >
        {sidebarCollapsed ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>

      {/* Mobile overlay */}
      {sidebarCollapsed && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={toggleSidebar}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed left-0 top-0 z-40 h-screen w-60 border-r border-slate-800 bg-slate-950/95 backdrop-blur-xl transition-transform",
          "md:translate-x-0",
          sidebarCollapsed ? "translate-x-0" : "-translate-x-full md:translate-x-0",
        )}
      >
        <div className="flex h-14 items-center gap-2 px-5 border-b border-slate-800">
          <Network className="h-5 w-5 text-indigo-400" />
          <span className="text-base font-bold tracking-tight">
            World<span className="text-indigo-400">RAG</span>
          </span>
        </div>

        <nav aria-label="Main navigation" className="mt-4 flex flex-col gap-6 px-3">
          {/* Dashboard */}
          <NavItem href="/" label="Dashboard" icon={LayoutDashboard} active={pathname === "/"} />

          {NAV_SECTIONS.map((section) => (
            <div key={section.label}>
              <div className="text-[10px] font-semibold uppercase tracking-widest text-slate-600 px-3 mb-2">
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
          <div className="rounded-lg bg-slate-900/50 border border-slate-800 p-3 text-xs text-slate-500">
            <div className="font-medium text-slate-400 mb-0.5">WorldRAG v0.2</div>
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
        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
        active
          ? "bg-indigo-600/10 text-indigo-400 border border-indigo-500/20"
          : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50",
      )}
    >
      <Icon className="h-4 w-4" />
      {label}
    </Link>
  )
}
