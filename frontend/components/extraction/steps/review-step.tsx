"use client"

import { useQuery } from "@tanstack/react-query"
import { ArrowRight, Loader2, Search } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { apiFetch } from "@/lib/api/client"
import { EntityReviewTable } from "@/components/extraction/review/entity-review-table"
import { RelationReviewTable } from "@/components/extraction/review/relation-review-table"
import { ProblemsPanel } from "@/components/extraction/review/problems-panel"
import { ErrorState } from "@/components/ui/error-state"
import { EmptyState } from "@/components/shared/empty-state"
import type { SubgraphData } from "@/lib/api/types"

interface ReviewStepProps {
  projectSlug: string
  bookId: string
  onContinue: () => void
}

export function ReviewStep({ projectSlug: _projectSlug, bookId, onContinue }: ReviewStepProps) {
  const { data: subgraph, isLoading, error } = useQuery({
    queryKey: ["graph", "subgraph", bookId],
    queryFn: () => apiFetch<SubgraphData>(`/graph/subgraph/${bookId}`),
    enabled: !!bookId,
    staleTime: 60_000,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error) {
    return <ErrorState title="Failed to load extraction results" error={error as Error} />
  }

  const nodes = subgraph?.nodes ?? []
  const edges = subgraph?.edges ?? []

  return (
    <div className="space-y-6">
      <Tabs defaultValue="entities">
        <TabsList>
          <TabsTrigger value="entities">
            Entities ({nodes.length})
          </TabsTrigger>
          <TabsTrigger value="relations">
            Relations ({edges.length})
          </TabsTrigger>
          <TabsTrigger value="problems">
            Problems
          </TabsTrigger>
        </TabsList>

        <TabsContent value="entities" className="mt-4">
          {nodes.length === 0 ? (
            <EmptyState
              icon={<Search className="h-8 w-8 text-muted-foreground" />}
              title="No entities found"
              description="The extraction didn't produce any entities for this book."
            />
          ) : (
            <EntityReviewTable entities={nodes} bookId={bookId} />
          )}
        </TabsContent>

        <TabsContent value="relations" className="mt-4">
          {edges.length === 0 ? (
            <EmptyState
              icon={<Search className="h-8 w-8 text-muted-foreground" />}
              title="No relations found"
            />
          ) : (
            <RelationReviewTable edges={edges} nodes={nodes} />
          )}
        </TabsContent>

        <TabsContent value="problems" className="mt-4">
          <ProblemsPanel bookId={bookId} />
        </TabsContent>
      </Tabs>

      <div className="flex justify-end">
        <Button onClick={onContinue}>
          Explore graph <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  )
}
