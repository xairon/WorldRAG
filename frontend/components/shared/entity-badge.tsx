"use client"

import Link from "next/link"
import {
  Users,
  Sparkles,
  Shield,
  Crown,
  Swords,
  MapPin,
  Gem,
  Bug,
  Flag,
  Lightbulb,
} from "lucide-react"
import { cn, labelBadgeClass } from "@/lib/utils"

const ENTITY_ICONS: Record<string, React.ElementType> = {
  Character: Users,
  Skill: Sparkles,
  Class: Shield,
  Title: Crown,
  Event: Swords,
  Location: MapPin,
  Item: Gem,
  Creature: Bug,
  Faction: Flag,
  Concept: Lightbulb,
}

interface EntityBadgeProps {
  name: string
  type: string
  clickable?: boolean
  size?: "sm" | "md"
  className?: string
}

export function EntityBadge({ name, type, clickable = true, size = "sm", className }: EntityBadgeProps) {
  const Icon = ENTITY_ICONS[type] ?? Lightbulb
  const badgeClass = labelBadgeClass(type)

  const content = (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border font-medium",
        size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs",
        badgeClass,
        clickable && "cursor-pointer hover:brightness-125 transition-all",
        className,
      )}
    >
      <Icon className={size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5"} />
      {name}
    </span>
  )

  if (clickable) {
    return (
      <Link href={`/entity/${encodeURIComponent(type)}/${encodeURIComponent(name)}`}>
        {content}
      </Link>
    )
  }

  return content
}
