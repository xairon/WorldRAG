import { useState } from "react"
import { AlertTriangle, ChevronDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible"
import { cn } from "@/lib/utils"

interface ErrorStateProps {
  title: string
  message?: string
  error?: Error | null
  onRetry?: () => void
}

export function ErrorState({ title, message, error, onRetry }: ErrorStateProps) {
  const [open, setOpen] = useState(false)

  return (
    <div className="flex flex-col items-center gap-4 py-12 text-center">
      <AlertTriangle className="h-10 w-10 text-destructive" />
      <div className="space-y-1">
        <p className="font-semibold text-foreground">{title}</p>
        {message && <p className="text-sm text-muted-foreground">{message}</p>}
      </div>

      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}

      {error && (
        <Collapsible open={open} onOpenChange={setOpen} className="w-full max-w-md">
          <CollapsibleTrigger asChild>
            <button className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors">
              Technical details
              <ChevronDown
                className={cn("h-3 w-3 transition-transform", open && "rotate-180")}
              />
            </button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <pre className="mt-2 rounded-md bg-muted p-3 text-left text-xs text-muted-foreground whitespace-pre-wrap break-all">
              {error.stack ?? error.message}
            </pre>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  )
}
