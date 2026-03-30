"use client"

import { useQuery } from "@tanstack/react-query"
import { apiFetch } from "@/lib/api/client"
import type { BookDetail } from "@/lib/api/types"

export function useBooks(projectSlug: string | null) {
  return useQuery({
    queryKey: ["books", projectSlug],
    queryFn: () => apiFetch<unknown[]>(`/projects/${projectSlug}/books`),
    enabled: !!projectSlug,
    staleTime: 30_000,
  })
}

export function useBookDetail(bookId: string | null) {
  return useQuery({
    queryKey: ["book", bookId],
    queryFn: () => apiFetch<BookDetail>(`/books/${bookId}`),
    enabled: !!bookId,
    staleTime: 30_000,
  })
}

export function useBookStats(bookId: string | null) {
  return useQuery({
    queryKey: ["book-stats", bookId],
    queryFn: () => apiFetch<Record<string, unknown>>(`/books/${bookId}/stats`),
    enabled: !!bookId,
    staleTime: 60_000,
  })
}

interface BookJobs {
  book_id: string
  book_status: string
  jobs: {
    extraction: { job_id: string; status: string }
    embedding: { job_id: string; status: string }
  }
}

export function useBookJobs(bookId: string | null, polling = false) {
  return useQuery({
    queryKey: ["book-jobs", bookId],
    queryFn: () => apiFetch<BookJobs>(`/books/${bookId}/jobs`),
    enabled: !!bookId,
    refetchInterval: polling ? 5_000 : false,
  })
}
