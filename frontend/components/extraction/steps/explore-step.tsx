"use client"

import Link from "next/link"
import { ExternalLink, Download } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { useBookStats } from "@/hooks/use-books"

interface ExploreStepProps {
  projectSlug: string
  bookId: string
  onStart: () => void
}

export function ExploreStep({ projectSlug, bookId, onStart: _onStart }: ExploreStepProps) {
  const { data: stats } = useBookStats(bookId)

  const totalNodes = stats
    ? Object.values(stats).reduce(
        (a: number, b) => a + (typeof b === "number" ? b : 0),
        0,
      )
    : null

  return (
    <Card className="border-emerald-500/30">
      <CardContent className="flex flex-col items-center gap-6 py-12">
        <div className="text-center">
          <h2 className="text-2xl font-bold">Your Knowledge Graph is ready</h2>
          <p className="text-muted-foreground mt-2">
            {totalNodes != null ? `${totalNodes} nodes extracted` : "Extraction complete"}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button asChild size="lg">
            <Link href={`/projects/${projectSlug}/graph?book=${bookId}`}>
              Open Graph Explorer <ExternalLink className="ml-1.5 h-4 w-4" />
            </Link>
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="lg">
                <Download className="mr-1.5 h-4 w-4" /> Export
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem asChild>
                <a href={`/api/projects/${projectSlug}/export/cypher`} target="_blank" rel="noreferrer">
                  Cypher
                </a>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <a href={`/api/projects/${projectSlug}/export/jsonld`} target="_blank" rel="noreferrer">
                  JSON-LD
                </a>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <a href={`/api/projects/${projectSlug}/export/csv`} target="_blank" rel="noreferrer">
                  CSV
                </a>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardContent>
    </Card>
  )
}
