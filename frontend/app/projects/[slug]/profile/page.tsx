"use client"
import { useState, useEffect } from "react"
import { useParams } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Brain, Tag, GitBranch, Regex } from "lucide-react"
import { apiFetch } from "@/lib/api/client"

interface SagaProfile {
  saga_id: string
  saga_name: string
  version: number
  entity_types: Array<{
    type_name: string
    description: string
    instances_found: string[]
    confidence: number
  }>
  text_patterns: Array<{
    pattern_regex: string
    extraction_type: string
    example: string
  }>
  relation_types: Array<{
    relation_name: string
    source_type: string
    target_type: string
    cardinality: string
    temporal: boolean
  }>
  narrative_systems: string[]
  estimated_complexity: string
}

export default function ProjectProfilePage() {
  const params = useParams<{ slug: string }>()
  const [profile, setProfile] = useState<SagaProfile | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch(`/saga-profiles/${params.slug}`)
      .then((res: unknown) => setProfile((res as { profile: SagaProfile }).profile))
      .catch(() => setProfile(null))
      .finally(() => setLoading(false))
  }, [params.slug])

  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading profile...</p>
  }

  if (!profile) {
    return (
      <Card className="border-dashed">
        <CardContent className="flex flex-col items-center justify-center py-16 gap-3">
          <Brain className="h-10 w-10 text-muted-foreground" />
          <p className="text-muted-foreground text-sm">No profile yet</p>
          <p className="text-xs text-muted-foreground">Extract a book to auto-induce the ontology.</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Badge variant="outline">{profile.estimated_complexity} complexity</Badge>
        <Badge variant="secondary">v{profile.version}</Badge>
        {profile.narrative_systems.map((s) => (
          <Badge key={s} variant="secondary" className="text-xs">{s}</Badge>
        ))}
      </div>

      {/* Entity Types */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Tag className="h-4 w-4" /> Induced Entity Types ({profile.entity_types.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {profile.entity_types.map((et) => (
              <div key={et.type_name} className="border rounded-lg p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm font-medium">{et.type_name}</span>
                  <Badge variant="outline" className="text-xs">
                    {Math.round(et.confidence * 100)}%
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">{et.description}</p>
                <div className="flex flex-wrap gap-1">
                  {et.instances_found.slice(0, 8).map((inst) => (
                    <Badge key={inst} variant="secondary" className="text-[10px]">{inst}</Badge>
                  ))}
                  {et.instances_found.length > 8 && (
                    <Badge variant="secondary" className="text-[10px]">+{et.instances_found.length - 8}</Badge>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Relation Types */}
      {profile.relation_types.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <GitBranch className="h-4 w-4" /> Induced Relations ({profile.relation_types.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {profile.relation_types.map((rt) => (
                <div key={rt.relation_name} className="flex items-center gap-2 text-sm font-mono">
                  <span>{rt.source_type}</span>
                  <span className="text-muted-foreground">-[{rt.relation_name}]-&gt;</span>
                  <span>{rt.target_type}</span>
                  <Badge variant="outline" className="text-[10px] ml-auto">{rt.cardinality}</Badge>
                  {rt.temporal && <Badge variant="secondary" className="text-[10px]">temporal</Badge>}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Patterns */}
      {profile.text_patterns.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Regex className="h-4 w-4" /> Text Patterns ({profile.text_patterns.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {profile.text_patterns.map((p, i) => (
                <div key={i} className="border rounded-lg p-3 space-y-1">
                  <div className="font-mono text-xs text-muted-foreground">{p.pattern_regex}</div>
                  <div className="text-xs">
                    <span className="text-muted-foreground">Type:</span> {p.extraction_type}
                  </div>
                  <div className="text-xs">
                    <span className="text-muted-foreground">Example:</span>{" "}
                    <code className="bg-muted px-1 py-0.5 rounded text-[11px]">{p.example}</code>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
