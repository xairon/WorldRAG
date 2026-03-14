"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Network,
  FolderOpen,
  Settings,
  Menu,
  X,
  ArrowLeft,
  BookOpen,
  MessageSquare,
  Brain,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useUIStore } from "@/stores/ui-store"
import { useProjectStore } from "@/stores/project-store"
import { motion } from "motion/react"

export function Sidebar() {
  const pathname = usePathname()
  const { mobileSidebarOpen, toggleSidebar } = useUIStore()
  const { currentProject } = useProjectStore()

  // Detect if we're inside a project
  const projectMatch = pathname.match(/^\/projects\/([^/]+)/)
  const currentSlug = projectMatch?.[1] ?? null

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
          <Link href="/" className="font-display text-base font-bold tracking-tight">
            World<span className="text-[var(--primary)]">RAG</span>
          </Link>
        </div>

        <nav aria-label="Main navigation" className="mt-4 flex flex-col gap-1 px-3">
          {currentSlug ? (
            <>
              {/* Back to projects */}
              <Link
                href="/"
                className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-muted-foreground hover:text-foreground hover:bg-accent transition-colors mb-3"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                All Projects
              </Link>

              {/* Project name */}
              <div className="px-3 mb-3">
                <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60 mb-1">
                  Project
                </div>
                <div className="text-sm font-medium truncate">
                  {currentProject?.name ?? currentSlug}
                </div>
              </div>

              {/* Project tabs as nav items */}
              <NavItem
                href={`/projects/${currentSlug}`}
                label="Books"
                icon={BookOpen}
                active={pathname === `/projects/${currentSlug}` || pathname === `/projects/${currentSlug}/`}
              />
              <NavItem
                href={`/projects/${currentSlug}/graph`}
                label="Graph"
                icon={Network}
                active={pathname.startsWith(`/projects/${currentSlug}/graph`)}
              />
              <NavItem
                href={`/projects/${currentSlug}/chat`}
                label="Chat"
                icon={MessageSquare}
                active={pathname.startsWith(`/projects/${currentSlug}/chat`)}
              />
              <NavItem
                href={`/projects/${currentSlug}/profile`}
                label="Profile"
                icon={Brain}
                active={pathname.startsWith(`/projects/${currentSlug}/profile`)}
              />
            </>
          ) : (
            <>
              {/* Dashboard */}
              <NavItem
                href="/"
                label="Projects"
                icon={FolderOpen}
                active={pathname === "/"}
              />
            </>
          )}
        </nav>

        <div className="absolute bottom-4 left-0 right-0 px-5">
          <div className="glass rounded-lg p-3 text-xs text-muted-foreground">
            <div className="mb-0.5 font-medium text-foreground">WorldRAG v2.0</div>
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
