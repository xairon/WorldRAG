"use client"
import { useEffect } from "react"
import { useParams, usePathname } from "next/navigation"
import Link from "next/link"
import { getProject } from "@/lib/api/projects"
import { useProjectStore } from "@/stores/project-store"
import { BookOpen, Network, MessageSquare, Brain } from "lucide-react"
import { cn } from "@/lib/utils"

const tabs = [
  { label: "Books", href: "", icon: BookOpen },
  { label: "Graph", href: "/graph", icon: Network },
  { label: "Chat", href: "/chat", icon: MessageSquare },
  { label: "Profile", href: "/profile", icon: Brain },
]

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  const params = useParams<{ slug: string }>()
  const pathname = usePathname()
  const { currentProject, setCurrentProject } = useProjectStore()

  useEffect(() => {
    getProject(params.slug).then(setCurrentProject).catch(() => {})
  }, [params.slug, setCurrentProject])

  const slug = params.slug

  return (
    <div className="space-y-6">
      {/* Project header */}
      <div>
        <h1 className="font-display text-3xl font-light tracking-tight">
          {currentProject?.name ?? slug}
        </h1>
        {currentProject?.description && (
          <p className="text-muted-foreground mt-1 text-sm">{currentProject.description}</p>
        )}
      </div>

      {/* Tab bar */}
      <nav className="flex gap-1 border-b border-border">
        {tabs.map((tab) => {
          const href = `/projects/${slug}${tab.href}`
          const isActive = tab.href === ""
            ? pathname === `/projects/${slug}` || pathname === `/projects/${slug}/`
            : pathname.startsWith(href)
          const Icon = tab.icon
          return (
            <Link
              key={tab.label}
              href={href}
              className={cn(
                "flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors",
                isActive
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
              )}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </Link>
          )
        })}
      </nav>

      {/* Tab content */}
      {children}
    </div>
  )
}
