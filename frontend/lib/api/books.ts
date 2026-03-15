import { apiFetch } from "./client"
import type { BookInfo, BookDetail, ChapterInfo, IngestionResult, ExtractionResult, DLQEntry } from "./types"

export function listBooks(): Promise<BookInfo[]> {
  return apiFetch("/books")
}

export function getBook(id: string): Promise<BookDetail> {
  return apiFetch(`/books/${id}`)
}

export async function getBookDetail(bookId: string): Promise<BookDetail> {
  return apiFetch<BookDetail>(`/books/${bookId}`)
}

export async function getChapterText(
  bookId: string,
  chapterNumber: number,
): Promise<{ book_id: string; chapter_number: number; title: string; text: string; word_count: number }> {
  return apiFetch(`/reader/books/${bookId}/chapters/${chapterNumber}/text`)
}

export async function getChapterParagraphs(
  bookId: string,
  chapterNumber: number,
): Promise<{
  book_id: string
  chapter_number: number
  title: string
  paragraphs: { index: number; type: string; text: string; html: string; char_start: number; char_end: number; speaker?: string; word_count: number }[]
  total_words: number
}> {
  return apiFetch(`/reader/books/${bookId}/chapters/${chapterNumber}/paragraphs`)
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

export async function deleteBook(bookId: string): Promise<void> {
  await apiFetch(`/books/${bookId}`, { method: "DELETE" })
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

// ── DLQ (Dead Letter Queue) ─────────────────────────────────────────────────

export function getDLQ(bookId?: string): Promise<{ count: number; entries: DLQEntry[] }> {
  const q = bookId ? `?book_id=${bookId}` : ""
  return apiFetch(`/admin/dlq${q}`)
}

export function retryDLQChapter(bookId: string, chapter: number): Promise<unknown> {
  return apiFetch(`/admin/dlq/retry/${bookId}/${chapter}`, { method: "POST" })
}

export function retryAllDLQ(): Promise<unknown> {
  return apiFetch(`/admin/dlq/retry-all`, { method: "POST" })
}
