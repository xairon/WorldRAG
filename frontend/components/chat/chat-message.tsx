"use client"

import { Bot, User, Info, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { SourceCard } from "./source-card"
import type { ChatMessage as ChatMessageType } from "@/hooks/use-chat-stream"

interface ChatMessageProps {
  message: ChatMessageType
}

export function ChatMessage({ message: msg }: ChatMessageProps) {
  const isUser = msg.role === "user"
  const isSystem = msg.role === "system"
  const isAssistant = msg.role === "assistant"

  return (
    <div className={cn("flex gap-3 max-w-3xl", isUser && "ml-auto flex-row-reverse")}>
      {/* Avatar */}
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
          isUser && "bg-indigo-600",
          isAssistant && "bg-slate-800 border border-slate-700",
          isSystem && "bg-slate-800/50 border border-slate-700",
        )}
      >
        {isUser && <User className="h-4 w-4" />}
        {isAssistant &&
          (msg.isStreaming && !msg.content ? (
            <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
          ) : (
            <Bot className="h-4 w-4 text-indigo-400" />
          ))}
        {isSystem && <Info className="h-4 w-4 text-slate-500" />}
      </div>

      {/* Bubble */}
      <div
        className={cn(
          "rounded-xl px-4 py-3 text-sm leading-relaxed min-w-0",
          isUser && "bg-indigo-600/20 border border-indigo-500/20 text-slate-200",
          isAssistant && "bg-slate-800/50 border border-slate-700 text-slate-300",
          isSystem && "bg-slate-900/50 border border-slate-800 text-slate-500 italic",
        )}
      >
        {/* Content */}
        {msg.isStreaming && !msg.content ? (
          <span className="text-slate-500">Searching Knowledge Graph...</span>
        ) : (
          <div className="whitespace-pre-wrap">{msg.content}</div>
        )}

        {/* Streaming cursor */}
        {msg.isStreaming && msg.content && (
          <span className="inline-block w-1.5 h-4 bg-indigo-400 animate-pulse rounded-sm ml-0.5 align-text-bottom" />
        )}

        {/* Sources */}
        {isAssistant && msg.sources && msg.sources.length > 0 && (
          <SourceCard
            sources={msg.sources}
            relatedEntities={msg.relatedEntities}
          />
        )}
      </div>
    </div>
  )
}
