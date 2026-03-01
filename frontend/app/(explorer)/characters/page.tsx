"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { Users, Loader2 } from "lucide-react"
import { motion } from "motion/react"
import { listBooks } from "@/lib/api"
import { listEntities } from "@/lib/api/graph"
import type { BookInfo, GraphNode } from "@/lib/api/types"
import { LABEL_COLORS } from "@/lib/utils"
import { Skeleton } from "@/components/ui/skeleton"

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04 } },
}

const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.25, 0.4, 0.25, 1] as const } },
}

export default function CharactersPage() {
  const [books, setBooks] = useState<BookInfo[]>([])
  const [bookId, setBookId] = useState("")
  const [characters, setCharacters] = useState<GraphNode[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    listBooks().then((b) => {
      setBooks(b)
      if (b.length === 1) setBookId(b[0].id)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!bookId) {
      setCharacters([])
      return
    }
    setLoading(true)
    listEntities(bookId, "Character", 200)
      .then((data) => setCharacters(data.entities))
      .catch(() => setCharacters([]))
      .finally(() => setLoading(false))
  }, [bookId])

  const selectedBook = books.find((b) => b.id === bookId)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Users className="h-6 w-6 text-primary" />
          <h1 className="text-2xl font-bold font-display tracking-tight">Characters</h1>
        </div>
        {loading && <Loader2 className="h-5 w-5 animate-spin text-primary" />}
      </div>

      {/* Book selector */}
      <select
        aria-label="Select book"
        value={bookId}
        onChange={(e) => setBookId(e.target.value)}
        className="glass rounded-lg px-3 py-2 text-sm text-foreground"
      >
        <option value="">Select a book</option>
        {books.map((b) => (
          <option key={b.id} value={b.id}>{b.title}</option>
        ))}
      </select>

      {/* Character grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
      ) : characters.length > 0 ? (
        <motion.div
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3"
          variants={container}
          initial="hidden"
          animate="show"
        >
          {characters.map((char) => (
            <motion.div key={char.id} variants={item}>
              <Link
                href={`/characters/${encodeURIComponent(char.name)}?book_id=${bookId}&chapter=${selectedBook?.total_chapters ?? 1}`}
                className="group rounded-xl glass-hover p-4 block transition-all"
              >
                <div className="flex items-start gap-3">
                  <div
                    className="mt-0.5 h-3 w-3 rounded-full shrink-0"
                    style={{ backgroundColor: LABEL_COLORS.Character ?? "#8b5cf6" }}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-sm group-hover:text-primary transition-colors truncate">
                      {char.canonical_name || char.name}
                    </p>
                    {char.description && (
                      <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{char.description}</p>
                    )}
                  </div>
                </div>
              </Link>
            </motion.div>
          ))}
        </motion.div>
      ) : bookId ? (
        <div className="rounded-xl glass border-dashed p-8 text-center">
          <p className="text-muted-foreground text-sm">No characters found. Try running extraction first.</p>
        </div>
      ) : (
        <div className="rounded-xl glass border-dashed p-8 text-center">
          <p className="text-muted-foreground text-sm">Select a book to browse its characters.</p>
        </div>
      )}
    </div>
  )
}
