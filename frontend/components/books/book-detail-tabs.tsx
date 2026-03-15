"use client"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { formatNumber } from "@/lib/utils"
import Link from "next/link"
import type { ChapterInfo } from "@/lib/api/types"
import { BookStatusBadge } from "@/components/books/book-status-badge"

interface BookDetailTabsProps {
  chapters: ChapterInfo[]
  slug: string
  bookId: string
}

export function BookDetailTabs({ chapters, slug, bookId }: BookDetailTabsProps) {
  return (
    <Tabs defaultValue="chapters" className="mt-8">
      <TabsList>
        <TabsTrigger value="chapters">Chapters ({chapters.length})</TabsTrigger>
        <TabsTrigger value="extraction">Extraction</TabsTrigger>
      </TabsList>

      <TabsContent value="chapters" className="mt-4">
        <div className="rounded-lg border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50 text-left text-xs font-medium text-muted-foreground">
                <th className="px-4 py-3 w-12">#</th>
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3 w-24 text-right">Words</th>
                <th className="px-4 py-3 w-24 text-right">Entities</th>
                <th className="px-4 py-3 w-28">Status</th>
              </tr>
            </thead>
            <tbody>
              {chapters.map((ch) => (
                <tr key={ch.number} className="border-b transition-colors hover:bg-muted/30">
                  <td className="px-4 py-3 font-mono text-muted-foreground">{ch.number}</td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/projects/${slug}/books/${bookId}/reader/${ch.number}`}
                      className="font-medium hover:text-primary transition-colors"
                    >
                      {ch.title || `Chapter ${ch.number}`}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                    {formatNumber(ch.word_count)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-muted-foreground">
                    {ch.entity_count > 0 ? formatNumber(ch.entity_count) : "\u2014"}
                  </td>
                  <td className="px-4 py-3">
                    <BookStatusBadge status={ch.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </TabsContent>

      <TabsContent value="extraction" className="mt-4">
        <div className="rounded-lg border p-6 text-center text-muted-foreground">
          <Link
            href={`/projects/${slug}/books/${bookId}/extraction`}
            className="text-primary hover:underline"
          >
            Open extraction dashboard →
          </Link>
        </div>
      </TabsContent>
    </Tabs>
  )
}
