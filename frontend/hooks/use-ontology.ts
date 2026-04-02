"use client"

import { useQuery } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api/client"
import type { OntologyData } from "@/lib/api/graph"

export function useOntology(bookId: string | null) {
  return useQuery({
    queryKey: ["ontology", bookId],
    queryFn: () => apiFetch<OntologyData>(`/graph/ontology/${bookId}`),
    enabled: !!bookId,
    staleTime: 5 * 60_000,
  })
}
