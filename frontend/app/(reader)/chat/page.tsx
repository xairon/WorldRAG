"use client"

import { useState, useRef, useEffect } from "react"
import { Send, Trash2, StopCircle } from "lucide-react"
import { listBooks } from "@/lib/api"
import type { BookInfo } from "@/lib/api"
import { useBookStore } from "@/stores/book-store"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { SpoilerGuard } from "@/components/chat/spoiler-guard"
import { ChatMessage } from "@/components/chat/chat-message"
import { useChatStream } from "@/hooks/use-chat-stream"

export default function ChatPage() {
  const { selectedBookId, book, spoilerChapter, setSpoilerChapter } = useBookStore()
  const [books, setBooks] = useState<BookInfo[]>([])
  const [bookId, setBookId] = useState(selectedBookId ?? "")
  const [input, setInput] = useState("")
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { messages, isStreaming, send, stop, clearMessages } = useChatStream()

  useEffect(() => {
    listBooks().then(setBooks).catch(() => {})
  }, [])

  useEffect(() => {
    if (selectedBookId) setBookId(selectedBookId)
  }, [selectedBookId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const totalChapters = book?.total_chapters ?? books.find((b) => b.id === bookId)?.total_chapters ?? 0

  function handleSend(e: React.FormEvent) {
    e.preventDefault()
    if (!input.trim() || isStreaming || !bookId) return
    send(input.trim(), bookId, spoilerChapter ?? undefined)
    setInput("")
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Chat</h1>
          <p className="text-slate-400 text-sm mt-1">Ask questions about your novels</p>
        </div>
        <div className="flex items-center gap-3">
          <SpoilerGuard
            maxChapter={spoilerChapter}
            totalChapters={totalChapters}
            onChange={setSpoilerChapter}
          />
          <select
            aria-label="Select book"
            value={bookId}
            onChange={(e) => setBookId(e.target.value)}
            className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
          >
            <option value="">Select a book...</option>
            {books.map((b) => (
              <option key={b.id} value={b.id}>{b.title}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 py-6">
        <div className="space-y-4" role="log" aria-live="polite">
          {messages.map((msg) => (
            <ChatMessage key={msg.id} message={msg} />
          ))}
          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      {/* Input */}
      <form onSubmit={handleSend} className="flex gap-3 pt-4 border-t border-slate-800">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={bookId ? "Ask about characters, events, lore..." : "Select a book first..."}
          disabled={!bookId || isStreaming}
          className="flex-1"
        />
        {isStreaming ? (
          <Button type="button" variant="outline" onClick={stop}>
            <StopCircle className="h-4 w-4" />
          </Button>
        ) : (
          <Button type="submit" disabled={!bookId || !input.trim()}>
            <Send className="h-4 w-4" />
          </Button>
        )}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={clearMessages}
          disabled={isStreaming || messages.length <= 1}
          className="text-slate-500 hover:text-slate-300"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </form>
    </div>
  )
}
