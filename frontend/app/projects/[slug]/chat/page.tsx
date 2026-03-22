"use client"

import { useEffect, useRef, useState, useCallback } from "react"
import { useParams } from "next/navigation"
import { MessageSquare, PanelLeftClose, PanelLeft } from "lucide-react"
import { useChatStream } from "@/hooks/use-chat-stream"
import { useChatStore } from "@/stores/chat-store"
import { apiFetch } from "@/lib/api/client"
import type { BookInfo } from "@/lib/api/types"
import { ThreadSidebar } from "@/components/chat/thread-sidebar"
import { ChatHeader } from "@/components/chat/chat-header"
import { ChatInput } from "@/components/chat/chat-input"
import { ChatMessage } from "@/components/chat/chat-message"
import { SpoilerGuard } from "@/components/chat/spoiler-guard"

export default function ChatPage() {
  const { slug } = useParams<{ slug: string }>()
  const [books, setBooks] = useState<BookInfo[]>([])
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const scrollRef = useRef<HTMLDivElement>(null)

  const selectedBookId = useChatStore((s) => s.selectedBookId)
  const spoilerMaxChapter = useChatStore((s) => s.spoilerMaxChapter)
  const setSpoilerMaxChapter = useChatStore((s) => s.setSpoilerMaxChapter)
  const threadId = useChatStore((s) => s.threadId)

  const { messages, isStreaming, send, stop, clearMessages } = useChatStream()

  // Fetch books for this project on mount
  const setSelectedBookId = useChatStore((s) => s.setSelectedBookId)

  useEffect(() => {
    let cancelled = false
    apiFetch<BookInfo[]>(`/projects/${slug}/books`)
      .then((data) => {
        if (cancelled) return
        setBooks(data)
        // Auto-select first extracted book if none selected
        if (!selectedBookId) {
          const extracted = data.filter(
            (b) => b.status === "extracted" || b.status === "embedded",
          )
          if (extracted.length > 0) {
            setSelectedBookId(extracted[0].book_id ?? extracted[0].id)
          }
        }
      })
      .catch(() => {
        // ignore — books will remain empty
      })
    return () => {
      cancelled = true
    }
  }, [slug])

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    const el = scrollRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [messages])

  const handleSend = useCallback(
    (query: string) => {
      if (!selectedBookId) return
      send(query, selectedBookId, spoilerMaxChapter ?? undefined, threadId ?? undefined)
    },
    [selectedBookId, spoilerMaxChapter, threadId, send],
  )

  // Books that have been extracted (status contains "extracted" or "embedded")
  const extractedBooks = books.filter(
    (b) => b.status === "extracted" || b.status === "embedded",
  )
  const hasExtractedBooks = extractedBooks.length > 0
  const selectedBook = books.find((b) => b.id === selectedBookId)

  // Map books for ChatHeader format
  const headerBooks = extractedBooks.map((b) => ({
    id: b.book_id ?? b.id,
    title: b.title ?? b.filename ?? "Untitled",
    totalChapters: b.total_chapters ?? b.chapters_count ?? 0,
  }))

  // Filter out system welcome message for display — show empty state instead
  const displayMessages = messages.filter((m) => m.role !== "system")

  return (
    <div className="flex h-[calc(100vh-3.5rem)] overflow-hidden">
      {/* Thread sidebar — visible on xl screens, togglable */}
      {sidebarOpen && (
        <div className="hidden xl:block">
          <ThreadSidebar />
        </div>
      )}

      {/* Main chat area */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Header row: sidebar toggle + book selector */}
        <div className="flex items-center border-b">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="hidden xl:flex h-full items-center px-3 text-muted-foreground hover:text-foreground"
            aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
          >
            {sidebarOpen ? (
              <PanelLeftClose className="h-4 w-4" />
            ) : (
              <PanelLeft className="h-4 w-4" />
            )}
          </button>
          <div className="flex-1">
            <ChatHeader books={headerBooks} />
          </div>
        </div>

        {/* Spoiler guard */}
        {selectedBook && selectedBook.total_chapters > 1 && (
          <div className="px-4 py-2 border-b">
            <SpoilerGuard
              maxChapter={spoilerMaxChapter}
              totalChapters={selectedBook.total_chapters}
              onChange={setSpoilerMaxChapter}
            />
          </div>
        )}

        {/* Messages scroll area */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6">
          {!hasExtractedBooks ? (
            // Disabled state: no extracted books
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
              <MessageSquare className="h-10 w-10 text-muted-foreground/50" />
              <p className="text-sm text-muted-foreground">
                Extract a book to start chatting.
              </p>
            </div>
          ) : displayMessages.length === 0 ? (
            // Empty state: book selected but no messages yet
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
              <MessageSquare className="h-10 w-10 text-muted-foreground/50" />
              <p className="text-sm text-muted-foreground">
                Ask anything about{" "}
                {selectedBook ? (
                  <span className="font-medium text-foreground">
                    {selectedBook.title}
                  </span>
                ) : (
                  "your book"
                )}
                .
              </p>
            </div>
          ) : (
            // Message list
            <div className="mx-auto max-w-3xl space-y-6">
              {displayMessages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  message={msg}
                  threadId={threadId ?? undefined}
                  bookId={selectedBookId ?? undefined}
                />
              ))}
            </div>
          )}
        </div>

        {/* Chat input — sticky bottom */}
        <ChatInput
          onSend={handleSend}
          onStop={stop}
          isStreaming={isStreaming}
          disabled={!selectedBookId || !hasExtractedBooks}
        />
      </div>
    </div>
  )
}
