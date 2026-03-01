"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import {
  BookOpen,
  Network,
  Upload,
  Search,
  Clock,
  Eye,
  MessageSquare,
  ArrowRight,
} from "lucide-react"
import { motion } from "motion/react"
import { getHealth, listBooks, getGraphStats } from "@/lib/api"
import type { BookInfo, GraphStats, HealthStatus } from "@/lib/api"
import { cn, statusColor, formatNumber, LABEL_COLORS } from "@/lib/utils"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useBookStore } from "@/stores/book-store"
import { AnimatedCounter } from "@/components/shared/animated-counter"

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06 } },
}

const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.25, 0.4, 0.25, 1] as const } },
}

const QUICK_ACTIONS = [
  { href: "/library", label: "Upload Book", icon: Upload, color: "#6366f1" },
  { href: "/chat", label: "Chat RAG", icon: MessageSquare, color: "#10b981" },
  { href: "/search", label: "Search Entities", icon: Search, color: "#f59e0b" },
  { href: "/graph", label: "Explore Graph", icon: Network, color: "#06b6d4" },
]

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [books, setBooks] = useState<BookInfo[]>([])
  const [stats, setStats] = useState<GraphStats | null>(null)
  const [loading, setLoading] = useState(true)
  const { setSelectedBookId } = useBookStore()

  useEffect(() => {
    async function load() {
      const [h, b, s] = await Promise.allSettled([
        getHealth(),
        listBooks(),
        getGraphStats(),
      ])
      if (h.status === "fulfilled") setHealth(h.value)
      if (b.status === "fulfilled") setBooks(b.value)
      if (s.status === "fulfilled") setStats(s.value)
      setLoading(false)
    }
    load()
  }, [])

  if (loading) {
    return (
      <div className="space-y-8">
        <div>
          <Skeleton className="h-10 w-56 mb-2" />
          <Skeleton className="h-4 w-72" />
        </div>
        <div className="flex gap-8">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i}>
              <Skeleton className="h-12 w-24 mb-1" />
              <Skeleton className="h-3 w-20" />
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-5 w-5 rounded-full" />
          ))}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-16 rounded-xl" />
          ))}
        </div>
        <div>
          <Skeleton className="h-6 w-24 mb-4" />
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-32 rounded-xl" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="space-y-8"
    >
      {/* Hero section */}
      <motion.div variants={item}>
        <h1 className="font-display text-4xl font-light tracking-tight">
          Your Universe
        </h1>
        <p className="text-muted-foreground mt-1">WorldRAG Knowledge Graph</p>
      </motion.div>

      {/* Big stat counters */}
      {stats && stats.total_nodes > 0 && (
        <motion.div variants={item} className="flex flex-wrap gap-8 mt-6">
          <div>
            <AnimatedCounter
              value={stats.total_nodes}
              className="font-display text-5xl font-light tracking-tight"
            />
            <p className="text-muted-foreground text-xs mt-1 uppercase tracking-wider">
              Nodes
            </p>
          </div>
          <div>
            <AnimatedCounter
              value={stats.total_relationships}
              className="font-display text-5xl font-light tracking-tight"
            />
            <p className="text-muted-foreground text-xs mt-1 uppercase tracking-wider">
              Relationships
            </p>
          </div>
          <div>
            <span className="font-display text-5xl font-light tracking-tight">
              {books.length}
            </span>
            <p className="text-muted-foreground text-xs mt-1 uppercase tracking-wider">
              Books
            </p>
          </div>
        </motion.div>
      )}

      {/* Infrastructure status */}
      {health && (
        <motion.div variants={item} className="flex flex-wrap items-center gap-3">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Status
          </span>
          {Object.entries(health.services).map(([service, status]) => (
            <span
              key={service}
              className="inline-flex items-center gap-1.5 text-xs text-muted-foreground"
            >
              <span
                className={cn(
                  "h-2 w-2 rounded-full",
                  status === "ok"
                    ? "bg-emerald-400"
                    : status === "not configured"
                      ? "bg-muted-foreground/30"
                      : "bg-red-400"
                )}
              />
              {service}
            </span>
          ))}
        </motion.div>
      )}

      {/* Entity type badges */}
      {stats && Object.entries(stats.nodes).length > 0 && (
        <motion.div variants={item} className="flex flex-wrap gap-2">
          {Object.entries(stats.nodes)
            .slice(0, 8)
            .map(([label, count]) => (
              <span
                key={label}
                className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs glass"
              >
                <span
                  className="h-2 w-2 rounded-full"
                  style={{
                    backgroundColor: LABEL_COLORS[label] ?? "#94a3b8",
                  }}
                />
                {label}{" "}
                <span className="font-mono text-muted-foreground">
                  {formatNumber(count)}
                </span>
              </span>
            ))}
        </motion.div>
      )}

      {/* Quick Actions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {QUICK_ACTIONS.map((action) => (
          <motion.div
            key={action.href}
            variants={item}
            whileHover={{ scale: 1.02 }}
            transition={{ type: "spring", stiffness: 400, damping: 25 }}
          >
            <Link href={action.href} className="group">
              <Card className="glass-hover">
                <CardContent className="pt-4 flex items-center gap-3">
                  <div
                    className="rounded-lg p-2"
                    style={{ backgroundColor: `${action.color}15` }}
                  >
                    <action.icon
                      className="h-4 w-4"
                      style={{ color: action.color }}
                    />
                  </div>
                  <span className="text-sm font-medium">{action.label}</span>
                </CardContent>
              </Card>
            </Link>
          </motion.div>
        ))}
      </div>

      {/* Books section */}
      <motion.div variants={item}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-lg font-semibold">Books</h2>
          <Button variant="link" size="sm" asChild>
            <Link href="/library" className="gap-1">
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </Button>
        </div>

        {books.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <BookOpen className="h-10 w-10 text-muted-foreground mb-3" />
              <p className="text-muted-foreground mb-3">No books uploaded yet</p>
              <Button asChild>
                <Link href="/library">Upload your first book</Link>
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {books.slice(0, 6).map((book) => (
              <Card
                key={book.id}
                className="glass-hover group cursor-pointer"
                onClick={() => setSelectedBookId(book.id)}
              >
                <CardContent className="pt-4">
                  <div className="flex items-start justify-between mb-2">
                    <Link
                      href={`/library/${book.id}`}
                      className="font-medium text-sm group-hover:text-primary transition-colors truncate"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {book.title}
                    </Link>
                    <span
                      className={cn(
                        "text-[10px] font-medium px-2 py-0.5 rounded-full border shrink-0 ml-2",
                        statusColor(book.status)
                      )}
                    >
                      {book.status}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground space-y-1">
                    {book.author && <div>by {book.author}</div>}
                    {book.series_name && (
                      <div>
                        {book.series_name}{" "}
                        {book.order_in_series && `#${book.order_in_series}`}
                      </div>
                    )}
                    <div>
                      <span className="font-mono">{book.total_chapters}</span>{" "}
                      chapters
                    </div>
                  </div>
                  {(book.status === "extracted" ||
                    book.status === "embedded") && (
                    <div className="flex gap-2 mt-3 pt-3 border-t border-[var(--border)]">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs"
                        asChild
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Link href={`/read/${book.id}/1`}>
                          <Eye className="h-3 w-3 mr-1" /> Read
                        </Link>
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs"
                        asChild
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Link href={`/graph?book_id=${book.id}`}>
                          <Network className="h-3 w-3 mr-1" /> Graph
                        </Link>
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs"
                        asChild
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Link href={`/timeline/${book.id}`}>
                          <Clock className="h-3 w-3 mr-1" /> Timeline
                        </Link>
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </motion.div>
    </motion.div>
  )
}
