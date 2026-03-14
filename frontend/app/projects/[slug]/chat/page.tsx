"use client"

import { useState, useEffect, useRef } from "react"
import { useParams } from "next/navigation"
import { Send, Trash2, StopCircle } from "lucide-react"
import { listProjectBooks } from "@/lib/api/projects"
import { useChatStore } from "@/stores/chat-store"
import { BookSelector } from "@/components/projects/book-selector"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { ChatMessage } from "@/components/chat/chat-message"
import { ThreadSidebar } from "@/components/chat/thread-sidebar"
import { useChatStream } from "@/hooks/use-chat-stream"

export default function ProjectChatPage() {
  const params = useParams<{ slug: string }>()
  const { threadId, setThreadId, addThread } = useChatStore()
  const [bookId, setBookId] = useState("")
  const [input, setInput] = useState("")
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { messages, isStreaming, send, stop, clearMessages } = useChatStream()

  // Load first book of the project
  useEffect(() => {
    listProjectBooks(params.slug)
      .then((books) => {
        const withBookId = books.find((b) => b.book_id)
        if (withBookId?.book_id) setBookId(withBookId.book_id)
      })
      .catch(() => {})
  }, [params.slug])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  function handleSend(e: React.FormEvent) {
    e.preventDefault()
    if (!input.trim() || isStreaming || !bookId) return

    let currentThreadId = threadId
    if (!currentThreadId) {
      currentThreadId = crypto.randomUUID()
      setThreadId(currentThreadId)
      addThread({
        id: currentThreadId,
        bookId,
        title: input.trim().slice(0, 80),
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      })
    }

    send(input.trim(), bookId, undefined, currentThreadId)
    setInput("")
  }

  function handleClear() {
    clearMessages()
    setThreadId(null)
  }

  return (
    <div className="flex h-[calc(100vh-16rem)] rounded-lg border bg-background/50 overflow-hidden">
      <ThreadSidebar />

      <div className="flex flex-1 flex-col min-w-0 p-4">
        {/* Messages */}
        <ScrollArea className="flex-1">
          <div className="space-y-4" role="log" aria-live="polite">
            {messages.length === 0 && (
              <p className="text-center text-sm text-muted-foreground py-12">
                {bookId ? "Ask a question about this saga..." : "No books extracted yet."}
              </p>
            )}
            {messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                message={msg}
                threadId={threadId ?? undefined}
                bookId={bookId || undefined}
              />
            ))}
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        {/* Book selector + Input */}
        <div className="flex items-center gap-3 pt-4 border-t border-border">
          <BookSelector slug={params.slug} value={bookId} onChange={setBookId} />
        </div>
        <form onSubmit={handleSend} className="flex gap-3 pt-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={bookId ? "Ask about characters, events, lore..." : "Extract a book first..."}
            disabled={!bookId || isStreaming}
            className="flex-1"
          />
          {isStreaming ? (
            <Button type="button" variant="outline" onClick={stop} aria-label="Stop generation">
              <StopCircle className="h-4 w-4" />
            </Button>
          ) : (
            <Button type="submit" disabled={!bookId || !input.trim()} aria-label="Send message">
              <Send className="h-4 w-4" />
            </Button>
          )}
          <Button type="button" variant="ghost" size="sm" onClick={handleClear} disabled={isStreaming || messages.length <= 1} aria-label="Clear conversation">
            <Trash2 className="h-4 w-4" />
          </Button>
        </form>
      </div>
    </div>
  )
}
