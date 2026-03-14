"use client"

import { Trash2, MessageSquare } from "lucide-react"
import { useChatStore } from "@/stores/chat-store"

export function ThreadSidebar() {
  const { threads, threadId, setThreadId, removeThread } = useChatStore()

  return (
    <div className="flex h-full w-60 shrink-0 flex-col border-r border-[var(--glass-border)] bg-muted/20">
      <div className="flex items-center justify-between border-b border-[var(--glass-border)] p-3">
        <h3 className="text-sm font-medium">Conversations</h3>
        <button
          onClick={() => setThreadId(null)}
          className="text-xs text-primary hover:underline"
        >
          New
        </button>
      </div>
      <div className="flex-1 overflow-y-auto">
        {threads.length === 0 && (
          <p className="px-3 py-4 text-xs text-muted-foreground">No conversations yet.</p>
        )}
        {threads.map((t) => (
          <div
            key={t.id}
            className={`flex cursor-pointer items-center gap-2 px-3 py-2 hover:bg-muted/50 ${
              t.id === threadId ? "bg-muted" : ""
            }`}
            onClick={() => setThreadId(t.id)}
          >
            <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm">{t.title || "Untitled"}</p>
              <p className="text-xs text-muted-foreground">
                {new Date(t.updatedAt).toLocaleDateString()}
              </p>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation()
                removeThread(t.id)
              }}
              className="p-1 text-muted-foreground hover:text-destructive"
              aria-label="Delete thread"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
