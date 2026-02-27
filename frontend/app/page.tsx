"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import {
  BookOpen,
  Network,
  Users,
  Sparkles,
  MapPin,
  Activity,
  ArrowRight,
  MessageSquare,
  Upload,
  Search,
  Clock,
  Eye,
} from "lucide-react"
import { getHealth, listBooks, getGraphStats } from "@/lib/api"
import type { BookInfo, GraphStats, HealthStatus } from "@/lib/api"
import { cn, statusColor, formatNumber } from "@/lib/utils"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useBookStore } from "@/stores/book-store"

const NODE_ICONS: Record<string, typeof Users> = {
  Character: Users,
  Skill: Sparkles,
  Location: MapPin,
}

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
          <Skeleton className="h-8 w-48 mb-2" />
          <Skeleton className="h-4 w-72" />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-slate-400 mt-1">WorldRAG Knowledge Graph Overview</p>
      </div>

      {health && (
        <Card>
          <CardContent className="pt-5">
            <h2 className="text-sm font-medium text-slate-400 mb-3 flex items-center gap-2">
              <Activity className="h-4 w-4" /> Infrastructure
            </h2>
            <div className="flex flex-wrap gap-2">
              {Object.entries(health.services).map(([service, status]) => (
                <span
                  key={service}
                  className={cn(
                    "rounded-lg px-3 py-1.5 text-xs font-medium border",
                    status === "ok"
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                      : status === "not configured"
                        ? "bg-slate-500/10 text-slate-500 border-slate-600/20"
                        : "bg-red-500/10 text-red-400 border-red-500/20",
                  )}
                >
                  {service}: {status}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {stats && stats.total_nodes > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Total Nodes" value={formatNumber(stats.total_nodes)} icon={<Network className="h-5 w-5 text-indigo-400" />} />
          <StatCard label="Relationships" value={formatNumber(stats.total_relationships)} icon={<ArrowRight className="h-5 w-5 text-cyan-400" />} />
          {Object.entries(stats.nodes).slice(0, 6).map(([label, count]) => {
            const Icon = NODE_ICONS[label] ?? Network
            return <StatCard key={label} label={label} value={formatNumber(count)} icon={<Icon className="h-5 w-5 text-slate-400" />} />
          })}
        </div>
      )}

      {/* Quick Actions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Link href="/library" className="group">
          <Card className="hover:border-indigo-500/30 transition-all">
            <CardContent className="pt-4 flex items-center gap-3">
              <Upload className="h-5 w-5 text-indigo-400" />
              <span className="text-sm font-medium group-hover:text-indigo-400 transition-colors">Upload Book</span>
            </CardContent>
          </Card>
        </Link>
        <Link href="/chat" className="group">
          <Card className="hover:border-emerald-500/30 transition-all">
            <CardContent className="pt-4 flex items-center gap-3">
              <MessageSquare className="h-5 w-5 text-emerald-400" />
              <span className="text-sm font-medium group-hover:text-emerald-400 transition-colors">Chat RAG</span>
            </CardContent>
          </Card>
        </Link>
        <Link href="/search" className="group">
          <Card className="hover:border-amber-500/30 transition-all">
            <CardContent className="pt-4 flex items-center gap-3">
              <Search className="h-5 w-5 text-amber-400" />
              <span className="text-sm font-medium group-hover:text-amber-400 transition-colors">Search Entities</span>
            </CardContent>
          </Card>
        </Link>
        <Link href="/graph" className="group">
          <Card className="hover:border-cyan-500/30 transition-all">
            <CardContent className="pt-4 flex items-center gap-3">
              <Network className="h-5 w-5 text-cyan-400" />
              <span className="text-sm font-medium group-hover:text-cyan-400 transition-colors">Explore Graph</span>
            </CardContent>
          </Card>
        </Link>
      </div>

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Books</h2>
          <Button variant="link" size="sm" asChild>
            <Link href="/library" className="gap-1">View all <ArrowRight className="h-3 w-3" /></Link>
          </Button>
        </div>

        {books.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12">
              <BookOpen className="h-10 w-10 text-slate-600 mb-3" />
              <p className="text-slate-500 mb-3">No books uploaded yet</p>
              <Button asChild><Link href="/library">Upload your first book</Link></Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {books.slice(0, 6).map((book) => (
              <Card key={book.id} className="group hover:border-slate-700 transition-all cursor-pointer" onClick={() => setSelectedBookId(book.id)}>
                <CardContent className="pt-4">
                  <div className="flex items-start justify-between mb-2">
                    <Link href={`/library/${book.id}`} className="font-medium text-sm group-hover:text-indigo-400 transition-colors truncate" onClick={(e) => e.stopPropagation()}>
                      {book.title}
                    </Link>
                    <span className={cn("text-[10px] font-medium px-2 py-0.5 rounded-full border shrink-0 ml-2", statusColor(book.status))}>
                      {book.status}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500 space-y-1">
                    {book.author && <div>by {book.author}</div>}
                    {book.series_name && <div>{book.series_name} {book.order_in_series && `#${book.order_in_series}`}</div>}
                    <div>{book.total_chapters} chapters</div>
                  </div>
                  {(book.status === "extracted" || book.status === "embedded") && (
                    <div className="flex gap-2 mt-3 pt-3 border-t border-slate-800">
                      <Button variant="ghost" size="sm" className="h-7 text-xs" asChild onClick={(e) => e.stopPropagation()}>
                        <Link href={`/read/${book.id}/1`}><Eye className="h-3 w-3 mr-1" /> Read</Link>
                      </Button>
                      <Button variant="ghost" size="sm" className="h-7 text-xs" asChild onClick={(e) => e.stopPropagation()}>
                        <Link href={`/graph?book_id=${book.id}`}><Network className="h-3 w-3 mr-1" /> Graph</Link>
                      </Button>
                      <Button variant="ghost" size="sm" className="h-7 text-xs" asChild onClick={(e) => e.stopPropagation()}>
                        <Link href={`/timeline/${book.id}`}><Clock className="h-3 w-3 mr-1" /> Timeline</Link>
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <Card>
      <CardContent className="pt-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-slate-500">{label}</span>
          {icon}
        </div>
        <div className="text-2xl font-bold tracking-tight">{value}</div>
      </CardContent>
    </Card>
  )
}
