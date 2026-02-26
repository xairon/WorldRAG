"use client"

import { useMemo } from "react"
import { cn, labelColor } from "@/lib/utils"
import type { EntityAnnotation } from "@/lib/api/reader"

interface AnnotationSidebarProps {
  annotations: EntityAnnotation[]
  className?: string
}

export function AnnotationSidebar({ annotations, className }: AnnotationSidebarProps) {
  // Group annotations by entity type, show events and notable entities
  const sidebarItems = useMemo(() => {
    const events = annotations.filter((a) => a.entity_type === "Event")
    const characters = annotations.filter((a) => a.entity_type === "Character")
    const skills = annotations.filter((a) => a.entity_type === "Skill")
    const locations = annotations.filter((a) => a.entity_type === "Location")

    // Deduplicate by name
    const dedup = (items: EntityAnnotation[]) => {
      const seen = new Set<string>()
      return items.filter((a) => {
        if (seen.has(a.entity_name)) return false
        seen.add(a.entity_name)
        return true
      })
    }

    return {
      events: dedup(events),
      characters: dedup(characters),
      skills: dedup(skills),
      locations: dedup(locations),
    }
  }, [annotations])

  const hasContent = Object.values(sidebarItems).some((items) => items.length > 0)

  if (!hasContent) return null

  return (
    <aside className={cn("space-y-4 text-xs", className)}>
      {sidebarItems.events.length > 0 && (
        <SidebarSection title="Events" items={sidebarItems.events} />
      )}
      {sidebarItems.characters.length > 0 && (
        <SidebarSection title="Characters" items={sidebarItems.characters} />
      )}
      {sidebarItems.skills.length > 0 && (
        <SidebarSection title="Skills" items={sidebarItems.skills} />
      )}
      {sidebarItems.locations.length > 0 && (
        <SidebarSection title="Locations" items={sidebarItems.locations} />
      )}
    </aside>
  )
}

function SidebarSection({
  title,
  items,
}: {
  title: string
  items: EntityAnnotation[]
}) {
  const color = labelColor(items[0]?.entity_type ?? "Concept")

  return (
    <div>
      <h4
        className="text-[10px] font-semibold uppercase tracking-wider mb-1.5"
        style={{ color }}
      >
        {title} ({items.length})
      </h4>
      <div className="space-y-1">
        {items.slice(0, 15).map((item) => (
          <div
            key={item.entity_name}
            className="px-2 py-1 rounded border border-slate-800 bg-slate-900/50 text-slate-400 hover:text-slate-300 transition-colors"
          >
            {item.entity_name}
          </div>
        ))}
      </div>
    </div>
  )
}
