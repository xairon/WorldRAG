"use client"

import { useCallback, useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Upload, BookOpen, ArrowRight, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { apiFetch } from "@/lib/api/client"
import { useBooks } from "@/hooks/use-books"
import { EmptyState } from "@/components/shared/empty-state"
import { ErrorState } from "@/components/ui/error-state"
import type { BookInfo, IngestionResult } from "@/lib/api/types"

interface UploadStepProps {
  projectSlug: string
  bookId: string
  onContinue: () => void
}

export function UploadStep({ projectSlug, bookId, onContinue }: UploadStepProps) {
  void bookId
  const queryClient = useQueryClient()
  const { data: books, isLoading, error } = useBooks(projectSlug)
  const [dragOver, setDragOver] = useState(false)

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append("file", file)
      form.append("book_num", String((books?.length ?? 0) + 1))
      return apiFetch<IngestionResult>(`/projects/${projectSlug}/books`, {
        method: "POST",
        body: form,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["books", projectSlug] })
    },
  })

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      const file = e.dataTransfer.files[0]
      if (file) uploadMutation.mutate(file)
    },
    [uploadMutation],
  )

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      if (file) uploadMutation.mutate(file)
    },
    [uploadMutation],
  )

  if (error) {
    return <ErrorState title="Failed to load books" error={error as Error} />
  }

  return (
    <div className="space-y-6">
      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`
          relative flex flex-col items-center justify-center gap-4 p-12
          border-2 border-dashed rounded-xl transition-colors cursor-pointer
          ${dragOver ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:border-muted-foreground/50"}
        `}
        onClick={() => document.getElementById("file-input")?.click()}
      >
        {uploadMutation.isPending ? (
          <>
            <Loader2 className="h-10 w-10 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Uploading & parsing...</p>
          </>
        ) : (
          <>
            <Upload className="h-10 w-10 text-muted-foreground" />
            <div className="text-center">
              <p className="text-sm font-medium">Drop your epub, pdf, or txt file here</p>
              <p className="text-xs text-muted-foreground mt-1">or click to browse</p>
            </div>
          </>
        )}
        <input
          id="file-input"
          type="file"
          accept=".epub,.pdf,.txt"
          className="hidden"
          onChange={handleFileInput}
        />
      </div>

      {/* Upload success */}
      {uploadMutation.isSuccess && uploadMutation.data && (
        <Card className="border-emerald-500/50">
          <CardContent className="flex items-center justify-between p-4">
            <div className="flex items-center gap-3">
              <BookOpen className="h-5 w-5 text-emerald-500" />
              <div>
                <p className="font-medium">{uploadMutation.data.title}</p>
                <p className="text-xs text-muted-foreground">
                  {uploadMutation.data.chapters_found} chapters &middot; {uploadMutation.data.chunks_created} chunks
                </p>
              </div>
            </div>
            <Button onClick={onContinue} size="sm">
              Configure <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
            </Button>
          </CardContent>
        </Card>
      )}

      {uploadMutation.isError && (
        <ErrorState
          title="Upload failed"
          message={(uploadMutation.error as Error).message}
          onRetry={() => uploadMutation.reset()}
        />
      )}

      {/* Existing books */}
      {!isLoading && books && books.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-3">Books in this project</h3>
          <div className="grid gap-3">
            {(books as BookInfo[]).map((book) => (
              <Card
                key={book.id ?? book.book_id}
                className="cursor-pointer hover:bg-accent/50 transition-colors"
                onClick={onContinue}
              >
                <CardContent className="flex items-center justify-between p-3">
                  <div className="flex items-center gap-3">
                    <BookOpen className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">
                      {book.filename ?? book.title ?? "Book"}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground">{book.status}</span>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {!isLoading && books && books.length === 0 && !uploadMutation.isSuccess && (
        <EmptyState
          title="No books yet"
          description="Upload your first book to get started."
        />
      )}
    </div>
  )
}
