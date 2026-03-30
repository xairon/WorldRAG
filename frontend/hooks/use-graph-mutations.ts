"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api/client"

export function useRenameEntity() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ entityId, name, canonicalName, description }: {
      entityId: string
      name?: string
      canonicalName?: string
      description?: string
    }) =>
      apiFetch<{ id: string; labels: string[]; updated_properties: string[] }>(
        `/graph/entity/${entityId}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            ...(name != null ? { name } : {}),
            ...(canonicalName != null ? { canonical_name: canonicalName } : {}),
            ...(description != null ? { description } : {}),
          }),
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["graph"] })
      queryClient.invalidateQueries({ queryKey: ["book-stats"] })
    },
  })
}

export function useDeleteEntity() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (entityId: string) =>
      apiFetch<{ deleted: boolean; relationships_removed: number }>(
        `/graph/entity/${entityId}`,
        { method: "DELETE" }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["graph"] })
      queryClient.invalidateQueries({ queryKey: ["book-stats"] })
    },
  })
}

export function useMergeEntities() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ sourceId, targetId }: { sourceId: string; targetId: string }) =>
      apiFetch<{ merged_into: string; aliases_added: string[]; relationships_transferred: number }>(
        "/graph/entities/merge",
        {
          method: "POST",
          body: JSON.stringify({ source_id: sourceId, target_id: targetId }),
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["graph"] })
      queryClient.invalidateQueries({ queryKey: ["book-stats"] })
    },
  })
}

export function useDeleteRelation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (relationshipId: string) =>
      apiFetch<{ deleted: boolean }>(
        `/graph/relationship/${relationshipId}`,
        { method: "DELETE" }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["graph"] })
    },
  })
}
