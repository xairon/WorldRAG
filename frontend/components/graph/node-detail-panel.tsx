"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import {
  X,
  Users,
  Sparkles,
  Shield,
  Swords,
  Crown,
  ExternalLink,
  Expand,
} from "lucide-react"
import { getCharacterProfile } from "@/lib/api/graph"
import type { GraphNode, CharacterProfile } from "@/lib/api/types"
import { EntityBadge } from "@/components/shared/entity-badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { labelColor } from "@/lib/utils"

interface NodeDetailPanelProps {
  node: GraphNode
  bookId?: string
  onClose: () => void
  onExpandNeighbors?: (nodeId: string) => void
}

export function NodeDetailPanel({ node, bookId, onClose, onExpandNeighbors }: NodeDetailPanelProps) {
  const [profile, setProfile] = useState<CharacterProfile | null>(null)
  const [loadingProfile, setLoadingProfile] = useState(false)

  const primaryLabel = node.labels?.[0] ?? "Concept"
  const isCharacter = node.labels?.includes("Character")

  useEffect(() => {
    if (!isCharacter || !node.name) return
    setLoadingProfile(true)
    getCharacterProfile(node.name, bookId)
      .then(setProfile)
      .catch(() => setProfile(null))
      .finally(() => setLoadingProfile(false))
  }, [node.name, node.labels, isCharacter, bookId])

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/80 backdrop-blur-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-800">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="h-3 w-3 rounded-full shrink-0"
            style={{ backgroundColor: labelColor(primaryLabel) }}
          />
          <h3 className="font-semibold text-sm truncate">{node.name}</h3>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-300 transition-colors">
          <X className="h-4 w-4" />
        </button>
      </div>

      <ScrollArea className="max-h-[calc(100vh-16rem)]">
        <div className="p-4 space-y-4">
          {/* Labels */}
          <div className="flex flex-wrap gap-1.5">
            {node.labels?.map((l) => (
              <EntityBadge key={l} name={l} type={l} clickable={false} size="sm" />
            ))}
          </div>

          {/* Description */}
          {node.description && (
            <p className="text-xs text-slate-400 leading-relaxed">{node.description}</p>
          )}

          {/* Actions */}
          <div className="flex gap-2">
            <Button variant="outline" size="sm" className="h-7 text-xs" asChild>
              <Link href={`/entity/${encodeURIComponent(primaryLabel)}/${encodeURIComponent(node.name)}`}>
                <ExternalLink className="h-3 w-3 mr-1" /> Wiki Page
              </Link>
            </Button>
            {onExpandNeighbors && (
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                onClick={() => onExpandNeighbors(node.id)}
              >
                <Expand className="h-3 w-3 mr-1" /> Expand
              </Button>
            )}
          </div>

          {/* Character profile */}
          {isCharacter && (
            <>
              <Separator />
              {loadingProfile ? (
                <div className="space-y-2">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-3/4" />
                </div>
              ) : profile ? (
                <div className="space-y-3">
                  {profile.skills.length > 0 && (
                    <ProfileSection title="Skills" icon={<Sparkles className="h-3 w-3 text-emerald-400" />}>
                      {profile.skills.map((s) => (
                        <div key={s.name} className="text-xs text-slate-400">
                          <EntityBadge name={s.name} type="Skill" size="sm" />
                          {s.rank && <span className="text-slate-600 ml-1">({s.rank})</span>}
                        </div>
                      ))}
                    </ProfileSection>
                  )}

                  {profile.classes.length > 0 && (
                    <ProfileSection title="Classes" icon={<Shield className="h-3 w-3 text-amber-400" />}>
                      {profile.classes.map((c) => (
                        <div key={c.name} className="text-xs text-slate-400">
                          <EntityBadge name={c.name} type="Class" size="sm" />
                          {c.tier && <span className="text-slate-600 ml-1">(T{c.tier})</span>}
                        </div>
                      ))}
                    </ProfileSection>
                  )}

                  {profile.titles.length > 0 && (
                    <ProfileSection title="Titles" icon={<Crown className="h-3 w-3 text-pink-400" />}>
                      {profile.titles.map((t) => (
                        <div key={t.name} className="text-xs text-slate-400">
                          <EntityBadge name={t.name} type="Title" size="sm" />
                        </div>
                      ))}
                    </ProfileSection>
                  )}

                  {profile.relationships.length > 0 && (
                    <ProfileSection title="Relationships" icon={<Users className="h-3 w-3 text-indigo-400" />}>
                      {profile.relationships.map((r, i) => (
                        <div key={i} className="text-xs text-slate-400 flex items-center gap-1">
                          <EntityBadge name={r.name} type="Character" size="sm" />
                          <span className="text-slate-600">({r.rel_type})</span>
                        </div>
                      ))}
                    </ProfileSection>
                  )}

                  {profile.events.length > 0 && (
                    <ProfileSection title="Events" icon={<Swords className="h-3 w-3 text-red-400" />}>
                      {profile.events.slice(0, 8).map((e) => (
                        <div key={e.name} className="text-xs text-slate-400">
                          <span className="font-medium text-red-400">{e.name}</span>
                          <span className="text-slate-600"> (ch.{e.chapter})</span>
                        </div>
                      ))}
                      {profile.events.length > 8 && (
                        <span className="text-[10px] text-slate-600">
                          +{profile.events.length - 8} more
                        </span>
                      )}
                    </ProfileSection>
                  )}
                </div>
              ) : null}
            </>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

function ProfileSection({
  title,
  icon,
  children,
}: {
  title: string
  icon: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <div>
      <div className="flex items-center gap-1.5 text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
        {icon} {title}
      </div>
      <div className="space-y-1">{children}</div>
    </div>
  )
}
