"use client"

import { useState, useEffect } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { ArrowRight, BookOpen, Network } from "lucide-react"
import { getEntityWiki } from "@/lib/api"
import type { EntityWiki } from "@/lib/api"
import { EntityBadge } from "@/components/shared/entity-badge"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { cn, labelColor } from "@/lib/utils"

/** Properties to hide from the properties section (internal/noisy). */
const HIDDEN_PROPS = new Set([
  "batch_id", "created_at", "book_id", "embedding",
])

export default function EntityWikiPage() {
  const params = useParams()
  const type = decodeURIComponent(params.type as string)
  const name = decodeURIComponent(params.name as string)

  const [wiki, setWiki] = useState<EntityWiki | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    getEntityWiki(type, name)
      .then(setWiki)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [type, name])

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-60 w-full" />
      </div>
    )
  }

  if (error || !wiki) {
    return (
      <div className="space-y-6">
        <EntityBadge name={name} type={type} clickable={false} size="md" />
        <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-8 text-center">
          <p className="text-red-400 text-sm">{error ?? "Entity not found"}</p>
        </div>
      </div>
    )
  }

  const color = labelColor(type)
  const visibleProps = Object.entries(wiki.properties).filter(
    ([key]) => !HIDDEN_PROPS.has(key) && !key.startsWith("_"),
  )

  return (
    <ScrollArea className="h-[calc(100vh-5rem)]">
      <div className="space-y-8 pb-12">
        {/* Header */}
        <div>
          <EntityBadge name={name} type={type} clickable={false} size="md" />
          {typeof wiki.properties.description === "string" && wiki.properties.description && (
            <p className="text-sm text-slate-400 mt-3 max-w-2xl leading-relaxed">
              {wiki.properties.description}
            </p>
          )}
        </div>

        {/* Properties */}
        {visibleProps.length > 0 && (
          <section>
            <h2 className="text-sm font-semibold text-slate-300 mb-3">Properties</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {visibleProps.map(([key, value]) => (
                <div
                  key={key}
                  className="rounded-lg bg-slate-900/50 border border-slate-800 px-3 py-2"
                >
                  <span className="text-[11px] text-slate-500 uppercase tracking-wider">
                    {key.replace(/_/g, " ")}
                  </span>
                  <p className="text-sm text-slate-300 mt-0.5 truncate">
                    {Array.isArray(value) ? value.join(", ") : String(value ?? "—")}
                  </p>
                </div>
              ))}
            </div>
          </section>
        )}

        <Separator className="bg-slate-800" />

        {/* Connections */}
        {Object.keys(wiki.connections).length > 0 && (
          <section>
            <div className="flex items-center gap-2 mb-3">
              <Network className="h-4 w-4 text-slate-500" />
              <h2 className="text-sm font-semibold text-slate-300">Connections</h2>
            </div>
            <div className="space-y-4">
              {Object.entries(wiki.connections).map(([relType, conns]) => (
                <div key={relType}>
                  <h3 className="text-xs text-slate-500 uppercase tracking-wider mb-2">
                    {relType.replace(/_/g, " ")} ({conns.length})
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {conns.map((conn, i) => (
                      <Link
                        key={`${conn.target_id}-${i}`}
                        href={`/entity/${encodeURIComponent(conn.target_label)}/${encodeURIComponent(conn.target_name)}`}
                        className="group flex items-center gap-1.5 rounded-lg bg-slate-900/50 border border-slate-800 px-3 py-1.5 text-xs hover:border-slate-600 transition-colors"
                      >
                        {conn.direction === "outgoing" && (
                          <ArrowRight className="h-3 w-3 text-slate-600" />
                        )}
                        <EntityBadge
                          name={conn.target_name}
                          type={conn.target_label}
                          clickable={false}
                          size="sm"
                        />
                      </Link>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        <Separator className="bg-slate-800" />

        {/* Appearances */}
        {wiki.appearances.length > 0 && (
          <section>
            <div className="flex items-center gap-2 mb-3">
              <BookOpen className="h-4 w-4 text-slate-500" />
              <h2 className="text-sm font-semibold text-slate-300">
                Appears in {wiki.appearances.length} chapter{wiki.appearances.length > 1 ? "s" : ""}
              </h2>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {wiki.appearances
                .filter((app, i, arr) => arr.findIndex((a) => a.chapter === app.chapter) === i)
                .map((app, i) => (
                <Badge
                  key={`ch-${app.chapter}-${i}`}
                  variant="outline"
                  className="text-xs border-slate-700 text-slate-400"
                >
                  Ch. {app.chapter}
                  {app.title ? ` — ${app.title}` : ""}
                </Badge>
              ))}
            </div>
          </section>
        )}
      </div>
    </ScrollArea>
  )
}
