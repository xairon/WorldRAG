"use client"

// Link removed — no standalone entity detail page
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
  Heart,
  Globe,
  Link2,
  Fingerprint,
  Theater,
  BookOpen,
  ScrollText,
  Palette,
  Layers,
  UserCheck,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { getEntityHex } from "@/lib/constants"

const ENTITY_ICONS: Record<string, React.ElementType> = {
  Character: Users,
  Skill: Sparkles,
  Class: Shield,
  Title: Crown,
  Event: Swords,
  Location: MapPin,
  Object: Gem,
  Creature: Bug,
  Faction: Flag,
  Concept: Lightbulb,
  Prophecy: ScrollText,
  Setting: Globe,
  PsychologicalState: Heart,
  SocialRelationship: Link2,
  CharacterFeature: Fingerprint,
  NarrativeRole: Theater,
  NarrativeSequence: BookOpen,
  CharacterStoff: UserCheck,
  NarrativeStoff: Layers,
  TextualFeature: Palette,
  Race: Users,
  Level: Sparkles,
  System: Shield,
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
  const hex = getEntityHex(type)

  const content = (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border font-medium",
        size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs",
        clickable && "cursor-pointer hover:brightness-125 transition-all",
        className,
      )}
      style={{ borderColor: hex, color: hex }}
    >
      <Icon className={size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5"} />
      {name}
    </span>
  )

  // Entity badge is display-only — no standalone entity page exists
  return content
}
