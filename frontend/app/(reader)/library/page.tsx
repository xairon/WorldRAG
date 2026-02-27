"use client"

import { useEffect, useState, useCallback } from "react"
import Link from "next/link"
import {
  Upload,
  BookOpen,
  Trash2,
  Zap,
  Loader2,
  X,
  Network,
  Eye,
  Clock,
  Telescope,
} from "lucide-react"
import { listBooks, uploadBook, deleteBook } from "@/lib/api"
import type { BookInfo } from "@/lib/api"
import { cn, statusColor } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { useBookStore } from "@/stores/book-store"

export default function LibraryPage() {
  const [books, setBooks] = useState<BookInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [showUpload, setShowUpload] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { setSelectedBookId } = useBookStore()

  const refresh = useCallback(async () => {
    try {
      setBooks(await listBooks())
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load books")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  async function handleUpload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setUploading(true)
    setError(null)
    const form = new FormData(e.currentTarget)
    try {
      await uploadBook(form)
      setShowUpload(false)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed")
    } finally {
      setUploading(false)
    }
  }

  async function handleDelete(bookId: string, title: string) {
    if (!confirm(`Delete "${title}" and all associated data?`)) return
    try {
      await deleteBook(bookId)
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed")
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Library</h1>
          <p className="text-slate-400 text-sm mt-1">
            Upload, process, and explore your novels
          </p>
        </div>
        <Button onClick={() => setShowUpload(!showUpload)}>
          <Upload className="h-4 w-4 mr-2" />
          Upload Book
        </Button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-4 text-red-400 text-sm flex items-center justify-between">
          {error}
          <button aria-label="Dismiss error" onClick={() => setError(null)}><X className="h-4 w-4" /></button>
        </div>
      )}

      {showUpload && (
        <Card>
          <CardContent className="pt-6">
            <form onSubmit={handleUpload} className="space-y-4">
              <h2 className="text-lg font-semibold">Upload a Book</h2>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label htmlFor="book-file" className="block text-sm text-slate-400 mb-1">File *</label>
                  <input
                    id="book-file"
                    type="file"
                    name="file"
                    accept=".epub,.pdf,.txt"
                    required
                    className="block w-full text-sm text-slate-300 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-indigo-600 file:text-white hover:file:bg-indigo-500 cursor-pointer"
                  />
                </div>
                <div>
                  <label htmlFor="book-title" className="block text-sm text-slate-400 mb-1">Title</label>
                  <Input id="book-title" name="title" placeholder="Auto-detected from filename" />
                </div>
                <div>
                  <label htmlFor="book-author" className="block text-sm text-slate-400 mb-1">Author</label>
                  <Input id="book-author" name="author" />
                </div>
                <div>
                  <label htmlFor="book-genre" className="block text-sm text-slate-400 mb-1">Genre</label>
                  <select
                    id="book-genre"
                    name="genre"
                    defaultValue="litrpg"
                    className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                  >
                    <option value="litrpg">LitRPG</option>
                    <option value="cultivation">Cultivation</option>
                    <option value="progression_fantasy">Progression Fantasy</option>
                    <option value="fantasy">Fantasy</option>
                    <option value="sci_fi">Sci-Fi</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="book-series" className="block text-sm text-slate-400 mb-1">Series</label>
                  <Input id="book-series" name="series_name" />
                </div>
                <div>
                  <label htmlFor="book-order" className="block text-sm text-slate-400 mb-1">Order in Series</label>
                  <Input id="book-order" type="number" name="order_in_series" min={1} />
                </div>
              </div>
              <div className="flex gap-3">
                <Button type="submit" disabled={uploading}>
                  {uploading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Upload className="h-4 w-4 mr-2" />}
                  {uploading ? "Uploading..." : "Upload & Ingest"}
                </Button>
                <Button type="button" variant="outline" onClick={() => setShowUpload(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="text-center py-12 text-slate-500">Loading books...</div>
      ) : books.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/30 p-12 text-center">
          <BookOpen className="h-12 w-12 text-slate-600 mx-auto mb-4" />
          <p className="text-slate-500 text-lg mb-2">No books yet</p>
          <p className="text-slate-600 text-sm">Upload an ePub, PDF, or TXT file to get started</p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {books.map((book) => (
            <Card
              key={book.id}
              className="group hover:border-slate-700 transition-all cursor-pointer"
              onClick={() => setSelectedBookId(book.id)}
            >
              <CardContent className="pt-5">
                <div className="flex items-start justify-between mb-3">
                  <div className="min-w-0 flex-1">
                    <Link
                      href={`/library/${book.id}`}
                      className="font-semibold text-sm group-hover:text-indigo-400 transition-colors block truncate"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {book.title}
                    </Link>
                    {book.author && (
                      <p className="text-xs text-slate-500 mt-0.5">by {book.author}</p>
                    )}
                  </div>
                  <span className={cn(
                    "text-[10px] font-medium px-2 py-0.5 rounded-full border shrink-0 ml-2",
                    statusColor(book.status),
                  )}>
                    {book.status}
                  </span>
                </div>

                <div className="flex items-center gap-3 text-xs text-slate-500 mb-4">
                  {book.series_name && (
                    <span>{book.series_name} {book.order_in_series ? `#${book.order_in_series}` : ""}</span>
                  )}
                  <span>{book.total_chapters} chapters</span>
                  <span>{book.genre}</span>
                </div>

                <div className="flex items-center gap-1.5 border-t border-slate-800 pt-3 -mx-1">
                  {book.status === "completed" && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 text-xs text-amber-400 hover:text-amber-300"
                      asChild
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Link href={`/pipeline/${book.id}`}>
                        <Zap className="h-3 w-3 mr-1" />
                        Extract
                      </Link>
                    </Button>
                  )}
                  {(book.status === "extracted" || book.status === "embedded") && (
                    <>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 text-xs text-indigo-400 hover:text-indigo-300"
                        asChild
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Link href={`/graph?book_id=${book.id}`}>
                          <Network className="h-3 w-3 mr-1" />
                          Graph
                        </Link>
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 text-xs text-emerald-400 hover:text-emerald-300"
                        asChild
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Link href={`/read/${book.id}/1`}>
                          <Eye className="h-3 w-3 mr-1" />
                          Read
                        </Link>
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 text-xs text-cyan-400 hover:text-cyan-300"
                        asChild
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Link href={`/timeline/${book.id}`}>
                          <Clock className="h-3 w-3 mr-1" />
                          Timeline
                        </Link>
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 text-xs text-violet-400 hover:text-violet-300"
                        asChild
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Link href={`/pipeline/${book.id}`}>
                          <Telescope className="h-3 w-3 mr-1" />
                          Pipeline
                        </Link>
                      </Button>
                    </>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 text-xs text-red-400 hover:text-red-300 ml-auto"
                    onClick={(e) => { e.stopPropagation(); handleDelete(book.id, book.title) }}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
