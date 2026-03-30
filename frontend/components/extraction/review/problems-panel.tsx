"use client"

import { AlertTriangle, RotateCcw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { useRetryChapter, useDLQEntries } from "@/hooks/use-extraction"
import { EmptyState } from "@/components/shared/empty-state"

interface ProblemsPanelProps {
  bookId: string
}

export function ProblemsPanel({ bookId }: ProblemsPanelProps) {
  const { data: dlq } = useDLQEntries(bookId)
  const retryMutation = useRetryChapter()

  const entries = dlq?.entries ?? []

  if (entries.length === 0) {
    return (
      <EmptyState
        title="No problems found"
        description="All chapters extracted successfully."
      />
    )
  }

  return (
    <div className="space-y-4">
      {/* Failed chapters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-destructive" />
            Failed chapters ({entries.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {entries.map((entry) => (
            <Collapsible key={`${entry.book_id}-${entry.chapter}`}>
              <div className="flex items-center justify-between p-2 rounded-lg bg-muted/50">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs">Ch. {entry.chapter}</span>
                  <span className="text-xs text-destructive">{entry.error_type}</span>
                </div>
                <div className="flex items-center gap-1">
                  <CollapsibleTrigger className="text-xs text-muted-foreground hover:underline">
                    Details
                  </CollapsibleTrigger>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={() => retryMutation.mutate({ bookId, chapter: entry.chapter })}
                    disabled={retryMutation.isPending}
                  >
                    <RotateCcw className="mr-1 h-3 w-3" /> Retry
                  </Button>
                </div>
              </div>
              <CollapsibleContent>
                <pre className="mt-1 p-2 text-xs text-muted-foreground bg-muted rounded overflow-auto max-h-24">
                  {entry.error_message}
                </pre>
              </CollapsibleContent>
            </Collapsible>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
