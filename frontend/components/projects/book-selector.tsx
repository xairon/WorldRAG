"use client"

import { useEffect, useState, useRef } from "react"
import { listProjectBooks, type ProjectBook } from "@/lib/api/projects"

interface BookSelectorProps {
  slug: string
  value: string
  onChange: (bookId: string) => void
}

export function BookSelector({ slug, value, onChange }: BookSelectorProps) {
  const [books, setBooks] = useState<ProjectBook[]>([])
  // H15: Track auto-selection with a ref to prevent infinite re-render
  const autoSelectedRef = useRef(false)

  useEffect(() => {
    listProjectBooks(slug)
      .then((result) => {
        const extracted = result.filter((b) => b.book_id)
        setBooks(extracted)
        // Auto-select first if none selected (only once)
        if (!autoSelectedRef.current && extracted.length > 0 && extracted[0].book_id) {
          onChange(extracted[0].book_id)
          autoSelectedRef.current = true
        }
      })
      .catch(() => {})
  }, [slug]) // H15: only slug dependency — removed value and onChange

  if (books.length <= 1) return null

  return (
    <select
      aria-label="Select book"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-lg border border-border bg-background px-3 py-1.5 text-sm focus:border-primary focus:outline-none"
    >
      {books.map((b) => (
        <option key={b.id} value={b.book_id ?? ""}>
          Book {b.book_num}: {b.filename.replace(/\.[^.]+$/, "")}
        </option>
      ))}
    </select>
  )
}
