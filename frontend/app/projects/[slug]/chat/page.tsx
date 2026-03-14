"use client"
import { useParams } from "next/navigation"

export default function ProjectChatPage() {
  const params = useParams<{ slug: string }>()

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Chat about <span className="font-medium text-foreground">{params.slug}</span>
      </p>
      <div className="h-[600px] rounded-lg border bg-background/50 flex items-center justify-center">
        <p className="text-muted-foreground text-sm">
          Chat interface — extract a book first to start asking questions.
        </p>
      </div>
    </div>
  )
}
