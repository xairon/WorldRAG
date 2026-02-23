"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Network,
  Zap,
  Loader2,
  BookOpen,
  Hash,
  FileText,
  Sparkles,
} from "lucide-react";
import { getBook, extractBook, getGraphStats } from "@/lib/api";
import type { BookDetail, GraphStats } from "@/lib/api";
import { cn, statusColor, formatNumber } from "@/lib/utils";

export default function BookDetailPage() {
  const params = useParams();
  const bookId = params.id as string;
  const [detail, setDetail] = useState<BookDetail | null>(null);
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [d, s] = await Promise.allSettled([
          getBook(bookId),
          getGraphStats(bookId),
        ]);
        if (d.status === "fulfilled") setDetail(d.value);
        else setError("Book not found");
        if (s.status === "fulfilled") setStats(s.value);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load book");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [bookId]);

  async function handleExtract() {
    setExtracting(true);
    setError(null);
    try {
      await extractBook(bookId);
      const d = await getBook(bookId);
      setDetail(d);
      const s = await getGraphStats(bookId);
      setStats(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Extraction failed");
    } finally {
      setExtracting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-pulse text-slate-500">Loading book...</div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="text-center py-20">
        <p className="text-red-400 mb-4">{error ?? "Book not found"}</p>
        <Link href="/books" className="text-indigo-400 hover:underline">Back to books</Link>
      </div>
    );
  }

  const { book, chapters } = detail;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link
            href="/books"
            className="text-sm text-slate-500 hover:text-slate-300 flex items-center gap-1 mb-2"
          >
            <ArrowLeft className="h-3 w-3" /> Back to books
          </Link>
          <h1 className="text-2xl font-bold tracking-tight">{book.title}</h1>
          <div className="flex items-center gap-3 mt-2 text-sm text-slate-400">
            {book.author && <span>by {book.author}</span>}
            {book.series_name && (
              <span>
                {book.series_name}
                {book.order_in_series ? ` #${book.order_in_series}` : ""}
              </span>
            )}
            <span
              className={cn(
                "text-[10px] font-medium px-2 py-0.5 rounded-full border",
                statusColor(book.status)
              )}
            >
              {book.status}
            </span>
          </div>
        </div>

        <div className="flex gap-2">
          {(book.status === "completed" || book.status === "extracted") && (
            <button
              onClick={handleExtract}
              disabled={extracting}
              className="inline-flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-500 disabled:opacity-50 transition-colors"
            >
              {extracting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
              {extracting ? "Extracting..." : "Run Extraction"}
            </button>
          )}
          <Link
            href={`/graph?book_id=${bookId}`}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
          >
            <Network className="h-4 w-4" />
            Graph Explorer
          </Link>
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-4 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MiniStat
          label="Chapters"
          value={String(book.total_chapters)}
          icon={<BookOpen className="h-4 w-4 text-slate-500" />}
        />
        <MiniStat
          label="Genre"
          value={book.genre}
          icon={<Sparkles className="h-4 w-4 text-slate-500" />}
        />
        {stats && (
          <>
            <MiniStat
              label="KG Nodes"
              value={formatNumber(stats.total_nodes)}
              icon={<Network className="h-4 w-4 text-indigo-400" />}
            />
            <MiniStat
              label="KG Relations"
              value={formatNumber(stats.total_relationships)}
              icon={<Network className="h-4 w-4 text-cyan-400" />}
            />
          </>
        )}
      </div>

      {/* Entity breakdown */}
      {stats && stats.total_nodes > 0 && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5">
          <h2 className="text-sm font-medium text-slate-400 mb-3">Entity Breakdown</h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(stats.nodes).map(([label, count]) => (
              <Link
                key={label}
                href={`/graph?book_id=${bookId}&label=${label}`}
                className="rounded-lg bg-slate-800/80 border border-slate-700 px-3 py-1.5 text-xs hover:border-indigo-500/50 transition-colors"
              >
                <span className="font-medium">{label}</span>{" "}
                <span className="text-slate-500">{formatNumber(count)}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Chapters */}
      <div>
        <h2 className="text-lg font-semibold mb-3">Chapters</h2>
        <div className="rounded-xl border border-slate-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-900/80 text-slate-400 text-xs uppercase tracking-wider">
                <th className="text-left px-4 py-2.5 font-medium w-16"><Hash className="h-3 w-3" /></th>
                <th className="text-left px-4 py-2.5 font-medium">Title</th>
                <th className="text-center px-4 py-2.5 font-medium">Words</th>
                <th className="text-center px-4 py-2.5 font-medium">Chunks</th>
                <th className="text-center px-4 py-2.5 font-medium">Entities</th>
                <th className="text-center px-4 py-2.5 font-medium">Regex</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {chapters.map((ch) => (
                <tr key={ch.number} className="hover:bg-slate-900/40 transition-colors">
                  <td className="px-4 py-2.5 text-slate-500 font-mono">{ch.number}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <FileText className="h-3.5 w-3.5 text-slate-600 shrink-0" />
                      <span className="truncate">{ch.title || `Chapter ${ch.number}`}</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-center text-slate-400">
                    {formatNumber(ch.word_count)}
                  </td>
                  <td className="px-4 py-2.5 text-center text-slate-400">{ch.chunk_count}</td>
                  <td className="px-4 py-2.5 text-center text-slate-400">{ch.entity_count}</td>
                  <td className="px-4 py-2.5 text-center text-slate-400">{ch.regex_matches}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function MiniStat({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-xs text-slate-500">{label}</span>
      </div>
      <div className="text-lg font-bold">{value}</div>
    </div>
  );
}
