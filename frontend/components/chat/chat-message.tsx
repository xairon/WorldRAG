"use client"

import { Bot, User, Info, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { CitationHighlight } from "./citation-highlight"
import { SourcePanel } from "./source-panel"
import { ConfidenceBadge } from "./confidence-badge"
import { FeedbackButtons } from "./feedback-buttons"
import type { ChatMessage as ChatMessageType } from "@/hooks/use-chat-stream"

interface ChatMessageProps {
  message: ChatMessageType
  threadId?: string
  bookId?: string
}

export function ChatMessage({ message: msg, threadId, bookId }: ChatMessageProps) {
  const isUser = msg.role === "user"
  const isSystem = msg.role === "system"
  const isAssistant = msg.role === "assistant"

  return (
    <div className={cn("flex gap-3 max-w-3xl", isUser && "ml-auto flex-row-reverse")}>
      {/* Avatar */}
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
          isUser && "bg-primary",
          isAssistant && "bg-accent border border-[var(--glass-border)]",
          isSystem && "bg-accent border border-[var(--glass-border)]",
        )}
      >
        {isUser && <User className="h-4 w-4" />}
        {isAssistant &&
          (msg.isStreaming && !msg.content ? (
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
          ) : (
            <Bot className="h-4 w-4 text-primary" />
          ))}
        {isSystem && <Info className="h-4 w-4 text-muted-foreground" />}
      </div>

      {/* Bubble */}
      <div
        className={cn(
          "rounded-xl px-4 py-3 text-sm leading-relaxed min-w-0",
          isUser && "bg-primary/20 border border-primary/20 text-foreground",
          isAssistant && "bg-accent border border-[var(--glass-border)] text-foreground",
          isSystem && "bg-[var(--glass-bg)] border border-[var(--glass-border)] text-muted-foreground italic",
        )}
      >
        {/* Content */}
        {msg.isStreaming && !msg.content ? (
          <span className="text-muted-foreground">Searching Knowledge Graph...</span>
        ) : isAssistant ? (
          <div className="whitespace-pre-wrap">
            <CitationHighlight text={msg.content} />
          </div>
        ) : (
          <div className="whitespace-pre-wrap">{msg.content}</div>
        )}

        {/* Streaming cursor */}
        {msg.isStreaming && msg.content && (
          <span className="inline-block w-1.5 h-4 bg-primary animate-pulse rounded-sm ml-0.5 align-text-bottom" />
        )}

        {/* Confidence badge + feedback (only for completed assistant messages) */}
        {isAssistant && !msg.isStreaming && msg.content && (
          <div className="mt-2 flex items-center gap-2">
            {msg.confidence != null && <ConfidenceBadge score={msg.confidence} />}
            {threadId && (
              <FeedbackButtons
                messageId={msg.id}
                threadId={threadId}
                bookId={bookId}
              />
            )}
          </div>
        )}

        {/* Collapsible sources */}
        {isAssistant && msg.sources && msg.sources.length > 0 && (
          <SourcePanel chunks={msg.sources} />
        )}
      </div>
    </div>
  )
}
