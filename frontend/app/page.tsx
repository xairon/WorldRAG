"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  BookOpen,
  Network,
  Users,
  Swords,
  MapPin,
  Sparkles,
  Activity,
  ArrowRight,
} from "lucide-react";
import { getHealth, listBooks, getGraphStats } from "@/lib/api";
import type { BookInfo, GraphStats, HealthStatus } from "@/lib/api";
import { cn, statusColor, formatNumber } from "@/lib/utils";

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [books, setBooks] = useState<BookInfo[]>([]);
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [h, b, s] = await Promise.allSettled([
          getHealth(),
          listBooks(),
          getGraphStats(),
        ]);
        if (h.status === "fulfilled") setHealth(h.value);
        if (b.status === "fulfilled") setBooks(b.value);
        if (s.status === "fulfilled") setStats(s.value);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load dashboard");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-pulse text-slate-500">Loading dashboard...</div>
      </div>
    );
  }

  const nodeIcons: Record<string, typeof Users> = {
    Character: Users,
    Skill: Sparkles,
    Event: Swords,
    Location: MapPin,
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-slate-400 mt-1">WorldRAG Knowledge Graph Overview</p>
      </div>

      {error && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-4 text-red-400 text-sm">
          {error}
        </div>
      )}

      {health && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
          <h2 className="text-sm font-medium text-slate-400 mb-3 flex items-center gap-2">
            <Activity className="h-4 w-4" /> Infrastructure
          </h2>
          <div className="flex flex-wrap gap-3">
            {Object.entries(health.services).map(([service, status]) => (
              <div
                key={service}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-xs font-medium border",
                  status === "ok"
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                    : status === "not configured"
                      ? "bg-slate-500/10 text-slate-500 border-slate-600/20"
                      : "bg-red-500/10 text-red-400 border-red-500/20"
                )}
              >
                {service}: {status}
              </div>
            ))}
          </div>
        </div>
      )}

      {stats && stats.total_nodes > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            label="Total Nodes"
            value={formatNumber(stats.total_nodes)}
            icon={<Network className="h-5 w-5 text-indigo-400" />}
          />
          <StatCard
            label="Relationships"
            value={formatNumber(stats.total_relationships)}
            icon={<ArrowRight className="h-5 w-5 text-cyan-400" />}
          />
          {Object.entries(stats.nodes)
            .slice(0, 6)
            .map(([label, count]) => {
              const Icon = nodeIcons[label] ?? Network;
              return (
                <StatCard
                  key={label}
                  label={label}
                  value={formatNumber(count)}
                  icon={<Icon className="h-5 w-5 text-slate-400" />}
                />
              );
            })}
        </div>
      )}

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Books</h2>
          <Link
            href="/books"
            className="text-sm text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
          >
            View all <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        {books.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/30 p-8 text-center">
            <BookOpen className="h-10 w-10 text-slate-600 mx-auto mb-3" />
            <p className="text-slate-500 mb-3">No books uploaded yet</p>
            <Link
              href="/books"
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
            >
              Upload your first book
            </Link>
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {books.slice(0, 6).map((book) => (
              <Link
                key={book.id}
                href={`/books/${book.id}`}
                className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 hover:bg-slate-800/50 hover:border-slate-700 transition-all group"
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-medium text-sm group-hover:text-indigo-400 transition-colors truncate">
                    {book.title}
                  </h3>
                  <span
                    className={cn(
                      "text-[10px] font-medium px-2 py-0.5 rounded-full border shrink-0 ml-2",
                      statusColor(book.status)
                    )}
                  >
                    {book.status}
                  </span>
                </div>
                <div className="text-xs text-slate-500 space-y-1">
                  {book.author && <div>by {book.author}</div>}
                  {book.series_name && (
                    <div>
                      {book.series_name}{" "}
                      {book.order_in_series && `#${book.order_in_series}`}
                    </div>
                  )}
                  <div>
                    {book.total_chapters} chapters &middot; {book.genre}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-slate-500">{label}</span>
        {icon}
      </div>
      <div className="text-2xl font-bold tracking-tight">{value}</div>
    </div>
  );
}
