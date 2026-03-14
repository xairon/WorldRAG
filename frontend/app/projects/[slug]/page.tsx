"use client"

import { useState, useEffect, useCallback } from "react"
import { useParams } from "next/navigation"
import { Upload, Play, BookOpen, FileText, Loader2 } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  uploadBookToProject,
  triggerExtraction,
  listProjectBooks,
  type ProjectBook,
} from "@/lib/api/projects"
import { toast } from "sonner"

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

export default function ProjectBooksPage() {
  const params = useParams<{ slug: string }>()
  const [books, setBooks] = useState<ProjectBook[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [extractingId, setExtractingId] = useState<string | null>(null)

  const fetchBooks = useCallback(async () => {
    try {
      const result = await listProjectBooks(params.slug)
      setBooks(result)
    } catch {
      // empty state
    } finally {
      setLoading(false)
    }
  }, [params.slug])

  useEffect(() => {
    fetchBooks()
  }, [fetchBooks])

  const handleUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (!file) return
      setUploading(true)
      try {
        const bookNum = books.length + 1
        const result = await uploadBookToProject(params.slug, file, bookNum)
        toast.success(`Uploaded: ${result.chapters_found} chapters found`)
        fetchBooks()
      } catch {
        toast.error("Upload failed")
      } finally {
        setUploading(false)
      }
    },
    [params.slug, books.length, fetchBooks],
  )

  const handleExtract = useCallback(
    async (bookId: string | null) => {
      const id = bookId ?? undefined
      setExtractingId(bookId)
      try {
        const result = await triggerExtraction(params.slug, id)
        toast.success(`Extraction started (${result.mode} mode)`)
      } catch {
        toast.error("Extraction failed to start")
      } finally {
        setExtractingId(null)
      }
    },
    [params.slug],
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Book list */}
      {books.length > 0 && (
        <div className="space-y-3">
          {books.map((book) => (
            <Card key={book.id} className="transition-colors hover:border-primary/20">
              <CardContent className="flex items-center gap-4 py-4">
                <div className="rounded-lg bg-muted/50 p-2.5">
                  <BookOpen className="h-5 w-5 text-muted-foreground" />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm truncate">
                      {book.filename}
                    </span>
                    <Badge variant="outline" className="text-[10px] shrink-0">
                      Book {book.book_num}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                    <span>{formatFileSize(book.file_size)}</span>
                    <span>{formatDate(book.uploaded_at)}</span>
                    {book.book_id ? (
                      <Badge
                        variant="secondary"
                        className="text-[10px] bg-emerald-500/10 text-emerald-500 border-emerald-500/20"
                      >
                        Parsed
                      </Badge>
                    ) : (
                      <Badge variant="secondary" className="text-[10px]">
                        Pending
                      </Badge>
                    )}
                  </div>
                </div>

                {book.book_id && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleExtract(book.book_id)}
                    disabled={extractingId === book.book_id}
                    className="shrink-0"
                  >
                    <Play className="h-3.5 w-3.5 mr-1.5" />
                    {extractingId === book.book_id ? "Starting..." : "Extract"}
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Upload zone */}
      <Card className="border-dashed">
        <CardContent className="flex flex-col items-center justify-center py-10 gap-4">
          <div className="rounded-full p-3 bg-muted/50">
            <Upload className="h-6 w-6 text-muted-foreground" />
          </div>
          <div className="text-center">
            <p className="text-sm font-medium">
              {books.length === 0
                ? "Upload the first book"
                : `Add book ${books.length + 1} to the saga`}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              EPUB, PDF, or TXT
            </p>
          </div>
          <label className="cursor-pointer">
            <input
              type="file"
              accept=".epub,.pdf,.txt"
              onChange={handleUpload}
              className="hidden"
              disabled={uploading}
            />
            <Button variant="outline" size="sm" disabled={uploading} asChild>
              <span>
                <FileText className="h-3.5 w-3.5 mr-1.5" />
                {uploading ? "Uploading..." : "Choose file"}
              </span>
            </Button>
          </label>
        </CardContent>
      </Card>

      {/* Extract all button */}
      {books.some((b) => b.book_id) && (
        <div className="flex justify-end">
          <Button
            onClick={() => handleExtract(null)}
            disabled={extractingId !== null}
            size="sm"
          >
            <Play className="h-4 w-4 mr-2" />
            Extract All Books
          </Button>
        </div>
      )}
    </div>
  )
}
