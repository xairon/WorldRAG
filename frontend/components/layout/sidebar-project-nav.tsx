"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Network, MessageCircle, Dna, Settings } from "lucide-react"
import { cn } from "@/lib/utils"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

const tools = [
  { label: "Graph", icon: Network, path: "graph" },
  { label: "Chat", icon: MessageCircle, path: "chat" },
  { label: "Ontology", icon: Dna, path: "profile" },
]

export function SidebarProjectNav({ slug, collapsed }: { slug: string; collapsed: boolean }) {
  const pathname = usePathname()

  function NavItem({ label, icon: Icon, href }: { label: string; icon: typeof Network; href: string }) {
    const isActive = pathname === href || pathname.startsWith(href + "/")
    const content = (
      <Link
        href={href}
        className={cn(
          "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
          collapsed && "justify-center px-2",
          isActive
            ? "bg-primary/10 text-primary font-medium"
            : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
        )}
      >
        <Icon className="h-4 w-4 shrink-0" />
        {!collapsed && <span>{label}</span>}
      </Link>
    )

    if (collapsed) {
      return (
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger asChild>{content}</TooltipTrigger>
            <TooltipContent side="right">{label}</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )
    }

    return content
  }

  return (
    <div className="space-y-0.5">
      {!collapsed && (
        <span className="px-3 text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
          Tools
        </span>
      )}
      {tools.map((t) => (
        <NavItem key={t.path} label={t.label} icon={t.icon} href={`/projects/${slug}/${t.path}`} />
      ))}
      <div className="mt-1">
        <NavItem label="Settings" icon={Settings} href={`/projects/${slug}/settings`} />
      </div>
    </div>
  )
}
