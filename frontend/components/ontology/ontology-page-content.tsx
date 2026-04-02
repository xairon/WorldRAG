"use client"

import { useMemo, useState } from "react"
import { useQueryState, parseAsString } from "nuqs"
import { Loader2 } from "lucide-react"
import { useBooks } from "@/hooks/use-books"
import { useOntology } from "@/hooks/use-ontology"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ErrorState } from "@/components/ui/error-state"
import { EmptyState } from "@/components/shared/empty-state"
import { StatCards } from "./stat-cards"
import { SchemaGraph } from "./schema-graph"
import { EntityTypeTable } from "./entity-type-table"
import { RelationTypeTable } from "./relation-type-table"

interface OntologyPageContentProps {
  slug: string
}

export function OntologyPageContent({ slug }: OntologyPageContentProps) {
  const [bookParam, setBookParam] = useQueryState("book", parseAsString)
  const [selectedType, setSelectedType] = useState<string | null>(null)

  const { data: booksRaw, isLoading: booksLoading } = useBooks(slug)

  const books = useMemo(() => {
    if (!booksRaw) return []
    return (booksRaw as Array<Record<string, unknown>>)
      .filter((b) => {
        const status = b.status as string
        return ["extracted", "embedded"].includes(status)
      })
      .map((b) => ({
        id: (b.book_id as string) ?? (b.id as string) ?? "",
        title: (b.original_filename as string) ?? (b.title as string) ?? "Book",
      }))
  }, [booksRaw])

  const effectiveBookId = bookParam ?? books[0]?.id ?? null

  const {
    data: ontology,
    isLoading: ontLoading,
    error: ontError,
    refetch,
  } = useOntology(effectiveBookId)

  if (booksLoading || ontLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (books.length === 0) {
    return (
      <EmptyState
        title="No extracted books"
        description="Extract a book first to view its ontology schema."
      />
    )
  }

  if (ontError) {
    return (
      <ErrorState
        title="Failed to load ontology"
        error={ontError as Error}
        onRetry={() => refetch()}
      />
    )
  }

  if (!ontology) return null

  return (
    <div className="space-y-6">
      {/* Header with book selector */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Ontology Schema</h1>
        {books.length > 1 && (
          <Select
            value={effectiveBookId ?? ""}
            onValueChange={(v) => setBookParam(v)}
          >
            <SelectTrigger className="w-48">
              <SelectValue placeholder="Select book" />
            </SelectTrigger>
            <SelectContent>
              {books.map((b) => (
                <SelectItem key={b.id} value={b.id}>
                  {b.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {/* Stat cards */}
      <StatCards
        totalEntities={ontology.stats.total_entities}
        totalRelations={ontology.stats.total_relations}
        entityTypes={ontology.stats.entity_type_count}
        relationTypes={ontology.stats.relation_type_count}
      />

      {/* Schema graph */}
      <SchemaGraph
        entityTypes={ontology.entity_types}
        schemaEdges={ontology.schema_edges}
        selectedType={selectedType}
        onSelectType={setSelectedType}
      />

      {/* Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <EntityTypeTable
          entityTypes={ontology.entity_types}
          selectedType={selectedType}
        />
        <RelationTypeTable
          relationTypes={ontology.relation_types}
          schemaEdges={ontology.schema_edges}
          selectedType={selectedType}
        />
      </div>
    </div>
  )
}
