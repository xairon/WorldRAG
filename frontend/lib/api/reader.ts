import { apiFetch } from "./client"

export interface ChapterText {
  book_id: string
  chapter_number: number
  title: string
  text: string
  word_count: number
}

export interface EntityAnnotation {
  entity_name: string
  entity_type: string
  char_offset_start: number
  char_offset_end: number
  extraction_text: string
  mention_type: string   // "langextract" | "direct_name" | "alias" | "pronoun"
  confidence: number     // 0.0-1.0
}

export interface ChapterEntities {
  book_id: string
  chapter_number: number
  annotations: EntityAnnotation[]
}

export function getChapterText(bookId: string, chapter: number): Promise<ChapterText> {
  return apiFetch(`/reader/books/${bookId}/chapters/${chapter}/text`)
}

export function getChapterEntities(bookId: string, chapter: number): Promise<ChapterEntities> {
  return apiFetch(`/reader/books/${bookId}/chapters/${chapter}/entities`)
}

export interface ParagraphData {
  index: number
  type: "narration" | "dialogue" | "blue_box" | "scene_break" | "header"
  text: string
  html: string
  char_start: number
  char_end: number
  speaker: string | null
  word_count: number
}

export interface ChapterParagraphs {
  book_id: string
  chapter_number: number
  title: string
  paragraphs: ParagraphData[]
  total_words: number
}

export function getChapterParagraphs(bookId: string, chapter: number): Promise<ChapterParagraphs> {
  return apiFetch(`/reader/books/${bookId}/chapters/${chapter}/paragraphs`)
}
