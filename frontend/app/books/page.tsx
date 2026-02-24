"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Upload,
  BookOpen,
  Trash2,
  Zap,
  Loader2,
  X,
} from "lucide-react";
import {
  listBooks,
  uploadBook,
  extractBook,
  deleteBook,
} from "@/lib/api";
import type { BookInfo } from "@/lib/api";
import { cn, statusColor } from "@/lib/utils";

export default function BooksPage() {
  const [books, setBooks] = useState<BookInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [extracting, setExtracting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setBooks(await listBooks());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load books");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  async function handleUpload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setUploading(true);
    setError(null);
    const form = new FormData(e.currentTarget);
    try {
      await uploadBook(form);
      setShowUpload(false);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleExtract(bookId: string) {
    setExtracting(bookId);
    setError(null);
    try {
      await extractBook(bookId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Extraction failed");
    } finally {
      setExtracting(null);
    }
  }

  async function handleDelete(bookId: string, title: string) {
    if (!confirm(`Delete "${title}" and all associated data?`)) return;
    try {
      await deleteBook(bookId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Books</h1>
          <p className="text-slate-400 text-sm mt-1">
            Upload, process, and explore your novels
          </p>
        </div>
        <button
          onClick={() => setShowUpload(!showUpload)}
          className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
        >
          <Upload className="h-4 w-4" />
          Upload Book
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-4 text-red-400 text-sm flex items-center justify-between">
          {error}
          <button aria-label="Dismiss error" onClick={() => setError(null)}><X className="h-4 w-4" /></button>
        </div>
      )}

      {/* Upload Form */}
      {showUpload && (
        <form
          onSubmit={handleUpload}
          className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 space-y-4"
        >
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
              <input
                id="book-title"
                type="text"
                name="title"
                placeholder="Auto-detected from filename"
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label htmlFor="book-author" className="block text-sm text-slate-400 mb-1">Author</label>
              <input
                id="book-author"
                type="text"
                name="author"
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
              />
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
              <input
                id="book-series"
                type="text"
                name="series_name"
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label htmlFor="book-order" className="block text-sm text-slate-400 mb-1">Order in Series</label>
              <input
                id="book-order"
                type="number"
                name="order_in_series"
                min={1}
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={uploading}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
            >
              {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
              {uploading ? "Uploading..." : "Upload & Ingest"}
            </button>
            <button
              type="button"
              onClick={() => setShowUpload(false)}
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-400 hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Books Table */}
      {loading ? (
        <div className="text-center py-12 text-slate-500">Loading books...</div>
      ) : books.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/30 p-12 text-center">
          <BookOpen className="h-12 w-12 text-slate-600 mx-auto mb-4" />
          <p className="text-slate-500 text-lg mb-2">No books yet</p>
          <p className="text-slate-600 text-sm">Upload an ePub, PDF, or TXT file to get started</p>
        </div>
      ) : (
        <div className="rounded-xl border border-slate-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-900/80 text-slate-400 text-xs uppercase tracking-wider">
                <th className="text-left px-4 py-3 font-medium">Title</th>
                <th className="text-left px-4 py-3 font-medium">Author</th>
                <th className="text-left px-4 py-3 font-medium">Genre</th>
                <th className="text-center px-4 py-3 font-medium">Chapters</th>
                <th className="text-center px-4 py-3 font-medium">Status</th>
                <th className="text-right px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {books.map((book) => (
                <tr key={book.id} className="hover:bg-slate-900/40 transition-colors">
                  <td className="px-4 py-3">
                    <Link
                      href={`/books/${book.id}`}
                      className="font-medium hover:text-indigo-400 transition-colors"
                    >
                      {book.title}
                    </Link>
                    {book.series_name && (
                      <div className="text-xs text-slate-500 mt-0.5">
                        {book.series_name}
                        {book.order_in_series ? ` #${book.order_in_series}` : ""}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-400">{book.author ?? "---"}</td>
                  <td className="px-4 py-3 text-slate-400">{book.genre}</td>
                  <td className="px-4 py-3 text-center">{book.total_chapters}</td>
                  <td className="px-4 py-3 text-center">
                    <span
                      className={cn(
                        "text-[10px] font-medium px-2 py-0.5 rounded-full border",
                        statusColor(book.status)
                      )}
                    >
                      {book.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      {book.status === "completed" && (
                        <button
                          onClick={() => handleExtract(book.id)}
                          disabled={extracting === book.id}
                          title="Run LLM extraction"
                          aria-label="Run LLM extraction"
                          className="rounded-md p-1.5 text-amber-400 hover:bg-amber-500/10 transition-colors disabled:opacity-50"
                        >
                          {extracting === book.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Zap className="h-4 w-4" />
                          )}
                        </button>
                      )}
                      <Link
                        href={`/graph?book_id=${book.id}`}
                        title="View in Graph Explorer"
                        className="rounded-md p-1.5 text-indigo-400 hover:bg-indigo-500/10 transition-colors"
                      >
                        <BookOpen className="h-4 w-4" />
                      </Link>
                      <button
                        onClick={() => handleDelete(book.id, book.title)}
                        title="Delete"
                        aria-label="Delete book"
                        className="rounded-md p-1.5 text-red-400 hover:bg-red-500/10 transition-colors"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
