"use client"

import { useCallback, useEffect, useState } from "react"
import { Loader2 } from "lucide-react"
import { apiFetch } from "@/lib/api/client"
import { getOntology } from "@/lib/api/graph"
import type { OntologyData } from "@/lib/api/graph"
import { StatCards } from "./stat-cards"
import { SchemaGraph } from "./schema-graph"
import { EntityTypeTable } from "./entity-type-table"
import { RelationTypeTable } from "./relation-type-table"

interface BookEntry {
  id: string
  book_id: string
  title?: string
  status?: string
}

export function OntologyDashboard({ slug }: { slug: string }) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [ontology, setOntology] = useState<OntologyData | null>(null)
  const [bookTitle, setBookTitle] = useState("")

  const load = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const books = await apiFetch<BookEntry[]>(`/projects/${slug}/books`)
      const extracted = books.filter((b) => b.status === "extracted" || b.status === "embedded")

      if (extracted.length === 0) {
        setError("No extracted books found. Run extraction first.")
        setLoading(false)
        return
      }

      const book = extracted[0]
      const bookId = book.book_id ?? book.id
      setBookTitle(book.title ?? "Untitled")

      const data = await getOntology(bookId)
      setOntology(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load ontology")
    } finally {
      setLoading(false)
    }
  }, [slug])

  useEffect(() => {
    load()
  }, [load])

  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    )
  }

  if (error || !ontology) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <p className="text-slate-500">{error || "No data"}</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
          Ontology
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Knowledge schema discovered from <span className="font-medium text-slate-700 dark:text-slate-300">{bookTitle}</span>
          {ontology.induced_types.length > 0 && (
            <> — {ontology.induced_types.length} types auto-induced</>
          )}
        </p>
      </div>

      {/* Stat cards */}
      <StatCards
        totalEntities={ontology.stats.total_entities}
        totalRelations={ontology.stats.total_relations}
        entityTypes={ontology.stats.entity_type_count}
        relationTypes={ontology.stats.relation_type_count}
      />

      {/* Schema graph */}
      <SchemaGraph entityTypes={ontology.entity_types} schemaEdges={ontology.schema_edges} />

      {/* Tables */}
      <div className="grid gap-6 lg:grid-cols-2">
        <EntityTypeTable entityTypes={ontology.entity_types} />
        <RelationTypeTable relationTypes={ontology.relation_types} schemaEdges={ontology.schema_edges} />
      </div>
    </div>
  )
}
