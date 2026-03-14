"use client"

import { useState, useEffect, useCallback } from "react"
import { useParams } from "next/navigation"
import { Upload, Play, BookOpen, FileText, Loader2, Trash2, AlertCircle } from "lucide-react"
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
  const [extracting, setExtracting] = useState(false)

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

      // Reset input so same file can be selected again
      e.target.value = ""

      setUploading(true)
      try {
        const bookNum = books.length + 1
        await uploadBookToProject(params.slug, file, bookNum)
        toast.success(`"${file.name}" uploaded successfully`)
        await fetchBooks()
      } catch (err) {
        const message = err instanceof Error ? err.message : "Upload failed"
        if (message.includes("409") || message.includes("already")) {
          toast.error("This file has already been uploaded")
        } else {
          toast.error(message)
        }
      } finally {
        setUploading(false)
      }
    },
    [params.slug, books.length, fetchBooks],
  )

  const handleExtract = useCallback(async () => {
    setExtracting(true)
    try {
      const result = await triggerExtraction(params.slug)
      toast.success(
        result.mode === "discovery"
          ? "Extraction started — this is the first book, ontology will be auto-discovered"
          : "Extraction started — using discovered ontology from first book"
      )
    } catch {
      toast.error("Extraction failed to start")
    } finally {
      setExtracting(false)
    }
  }, [params.slug])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const hasBooks = books.length > 0

  return (
    <div className="space-y-6">
      {/* Step indicator */}
      {!hasBooks && (
        <Card className="border-primary/20 bg-primary/5">
          <CardContent className="py-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-primary mt-0.5 shrink-0" />
              <div className="text-sm">
                <p className="font-medium">Getting started</p>
                <p className="text-muted-foreground mt-1">
                  1. Upload an EPUB file below<br />
                  2. Click "Start Extraction" to build the knowledge graph<br />
                  3. Explore the graph and chat in the other tabs
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Book list */}
      {hasBooks && (
        <div className="space-y-3">
          {books.map((book, idx) => (
            <Card key={book.id} className="transition-colors hover:border-primary/20">
              <CardContent className="flex items-center gap-4 py-4">
                <div className="rounded-lg bg-muted/50 p-2.5">
                  <BookOpen className="h-5 w-5 text-muted-foreground" />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm truncate">
                      {book.filename.replace(/\.[^.]+$/, "")}
                    </span>
                    <Badge variant="outline" className="text-[10px] shrink-0">
                      Book {idx + 1}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                    <span>{formatFileSize(book.file_size)}</span>
                    <span>{formatDate(book.uploaded_at)}</span>
                    <Badge variant="secondary" className="text-[10px]">
                      Uploaded
                    </Badge>
                  </div>
                </div>
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
              {!hasBooks ? "Upload the first book of the saga" : `Add book ${books.length + 1}`}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              EPUB, PDF, or TXT — max 100 MB
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

      {/* Extract button */}
      {hasBooks && (
        <Card className="bg-primary/5 border-primary/20">
          <CardContent className="flex items-center justify-between py-4">
            <div>
              <p className="text-sm font-medium">Build Knowledge Graph</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {books.length === 1
                  ? "Discovery mode — WorldRAG will analyze the book and discover the universe's ontology"
                  : `Guided mode — uses the ontology discovered from book 1 to extract ${books.length} books`}
              </p>
            </div>
            <Button
              onClick={handleExtract}
              disabled={extracting}
              className="shrink-0"
            >
              <Play className="h-4 w-4 mr-2" />
              {extracting ? "Starting..." : "Start Extraction"}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
