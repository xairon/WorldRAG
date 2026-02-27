import { apiFetch } from "./client"
import type { BookInfo, BookDetail, IngestionResult, ExtractionResult } from "./types"

export function listBooks(): Promise<BookInfo[]> {
  return apiFetch("/books")
}

export function getBook(id: string): Promise<BookDetail> {
  return apiFetch(`/books/${id}`)
}

export function getBookStats(id: string): Promise<Record<string, unknown>> {
  return apiFetch(`/books/${id}/stats`)
}

export function uploadBook(form: FormData): Promise<IngestionResult> {
  return apiFetch("/books", { method: "POST", body: form })
}

export function extractBook(
  id: string,
  opts?: { chapters?: number[] },
): Promise<ExtractionResult> {
  return apiFetch(`/books/${id}/extract`, {
    method: "POST",
    body: JSON.stringify(opts?.chapters ? { chapters: opts.chapters } : {}),
  })
}

export function deleteBook(id: string): Promise<{ deleted: boolean }> {
  return apiFetch(`/books/${id}`, { method: "DELETE" })
}

export interface BookJobStatus {
  job_id: string
  status: string
}

export interface BookJobs {
  book_id: string
  book_status: string
  jobs: {
    extraction: BookJobStatus
    embedding: BookJobStatus
  }
}

export function getBookJobs(id: string): Promise<BookJobs> {
  return apiFetch(`/books/${id}/jobs`)
}
