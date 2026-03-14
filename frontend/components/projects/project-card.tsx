"use client"

import Link from "next/link"
import { BookOpen, Brain, Database } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface ProjectCardProps {
  slug: string
  name: string
  description: string
  booksCount: number
  hasProfile: boolean
  entityCount: number
  updatedAt: string
}

function formatRelativeDate(iso: string): string {
  const date = new Date(iso)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return "Today"
  if (diffDays === 1) return "Yesterday"
  if (diffDays < 30) return `${diffDays}d ago`
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`
  return `${Math.floor(diffDays / 365)}y ago`
}

export function ProjectCard({
  slug,
  name,
  description,
  booksCount,
  hasProfile,
  entityCount,
  updatedAt,
}: ProjectCardProps) {
  return (
    <Link href={`/projects/${slug}`} className="group">
      <Card className="glass-hover h-full transition-all duration-200 group-hover:border-primary/30">
        <CardContent className="pt-5 pb-4 flex flex-col gap-3">
          <div>
            <h3 className="font-semibold text-sm truncate group-hover:text-primary transition-colors">
              {name}
            </h3>
            {description && (
              <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                {description}
              </p>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <Badge
              variant="secondary"
              className="text-[10px] gap-1 px-1.5 py-0"
            >
              <BookOpen className="h-3 w-3" />
              {booksCount} {booksCount === 1 ? "book" : "books"}
            </Badge>
            <Badge
              variant="secondary"
              className="text-[10px] gap-1 px-1.5 py-0"
            >
              <Database className="h-3 w-3" />
              {entityCount}
            </Badge>
            <Badge
              variant="outline"
              className={cn(
                "text-[10px] gap-1 px-1.5 py-0",
                hasProfile
                  ? "border-emerald-500/30 text-emerald-400"
                  : "border-border text-muted-foreground"
              )}
            >
              <Brain className="h-3 w-3" />
              {hasProfile ? "Profile induced" : "No profile yet"}
            </Badge>
          </div>

          <div className="text-[10px] text-muted-foreground mt-auto">
            Updated {formatRelativeDate(updatedAt)}
          </div>
        </CardContent>
      </Card>
    </Link>
  )
}
