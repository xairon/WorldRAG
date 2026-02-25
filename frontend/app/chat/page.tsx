"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Loader2, Info, BookOpen } from "lucide-react";
import { listBooks, chatQuery } from "@/lib/api";
import type { BookInfo, SourceChunk, RelatedEntity } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  sources?: SourceChunk[];
  relatedEntities?: RelatedEntity[];
}

export default function ChatPage() {
  const [books, setBooks] = useState<BookInfo[]>([]);
  const [bookId, setBookId] = useState("");
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "system",
      content:
        "Welcome to WorldRAG Chat! Select a book and ask questions about the story, characters, events, or lore. The answers are grounded in the Knowledge Graph extracted from the novel.",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listBooks().then(setBooks).catch((err) => console.error("Failed to load books:", err));
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function toggleSources(msgId: string) {
    setExpandedSources((prev) => {
      const next = new Set(prev);
      if (next.has(msgId)) {
        next.delete(msgId);
      } else {
        next.add(msgId);
      }
      return next;
    });
  }

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || loading || !bookId) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const response = await chatQuery(userMsg.content, bookId);
      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: response.answer,
        timestamp: new Date(),
        sources: response.sources,
        relatedEntities: response.related_entities,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const errorMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: `Sorry, I encountered an error: ${err instanceof Error ? err.message : "Unknown error"}. Please try again.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-800">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Chat</h1>
          <p className="text-slate-400 text-sm mt-1">
            Ask questions about your novels
          </p>
        </div>
        <select
          aria-label="Select book"
          value={bookId}
          onChange={(e) => setBookId(e.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
        >
          <option value="">Select a book...</option>
          {books.map((b) => (
            <option key={b.id} value={b.id}>
              {b.title}
            </option>
          ))}
        </select>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto py-6 space-y-4" role="log" aria-live="polite">
        {messages.map((msg) => (
          <div key={msg.id}>
            <div
              className={cn(
                "flex gap-3 max-w-3xl",
                msg.role === "user" ? "ml-auto flex-row-reverse" : ""
              )}
            >
              <div
                className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
                  msg.role === "user"
                    ? "bg-indigo-600"
                    : msg.role === "assistant"
                      ? "bg-slate-800 border border-slate-700"
                      : "bg-slate-800/50 border border-slate-700"
                )}
              >
                {msg.role === "user" ? (
                  <User className="h-4 w-4" />
                ) : msg.role === "assistant" ? (
                  <Bot className="h-4 w-4 text-indigo-400" />
                ) : (
                  <Info className="h-4 w-4 text-slate-500" />
                )}
              </div>
              <div
                className={cn(
                  "rounded-xl px-4 py-3 text-sm leading-relaxed",
                  msg.role === "user"
                    ? "bg-indigo-600/20 border border-indigo-500/20 text-slate-200"
                    : msg.role === "assistant"
                      ? "bg-slate-800/50 border border-slate-700 text-slate-300"
                      : "bg-slate-900/50 border border-slate-800 text-slate-500 italic"
                )}
              >
                <div className="whitespace-pre-wrap">{msg.content}</div>

                {/* Sources toggle */}
                {msg.sources && msg.sources.length > 0 && (
                  <button
                    type="button"
                    onClick={() => toggleSources(msg.id)}
                    className="mt-2 flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
                  >
                    <BookOpen className="h-3 w-3" />
                    {expandedSources.has(msg.id) ? "Hide" : "Show"} {msg.sources.length} source{msg.sources.length > 1 ? "s" : ""}
                  </button>
                )}
              </div>
            </div>

            {/* Expanded sources */}
            {msg.sources && expandedSources.has(msg.id) && (
              <div className="ml-11 mt-2 space-y-2 max-w-3xl">
                {msg.sources.map((src, i) => (
                  <div
                    key={i}
                    className="rounded-lg bg-slate-900/50 border border-slate-800 px-3 py-2 text-xs"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-indigo-400 font-medium">
                        Chapter {src.chapter_number}
                        {src.chapter_title ? ` — ${src.chapter_title}` : ""}
                      </span>
                      <span className="text-slate-600">
                        relevance: {(src.relevance_score * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="text-slate-500 line-clamp-3">{src.text}</p>
                  </div>
                ))}

                {/* Related entities */}
                {msg.relatedEntities && msg.relatedEntities.length > 0 && (
                  <div className="rounded-lg bg-slate-900/50 border border-slate-800 px-3 py-2 text-xs">
                    <span className="text-slate-500 font-medium">Related entities: </span>
                    {msg.relatedEntities.map((e, i) => (
                      <span key={i} className="inline-block mr-2">
                        <span className="text-indigo-400">{e.name}</span>
                        <span className="text-slate-600"> ({e.label})</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-800 border border-slate-700">
              <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
            </div>
            <div className="rounded-xl bg-slate-800/50 border border-slate-700 px-4 py-3 text-sm text-slate-500">
              Searching Knowledge Graph...
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={handleSend}
        className="flex gap-3 pt-4 border-t border-slate-800"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            bookId
              ? "Ask about characters, events, lore..."
              : "Select a book first..."
          }
          disabled={!bookId || loading}
          className="flex-1 rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-sm focus:border-indigo-500 focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          aria-label="Send message"
          disabled={!bookId || !input.trim() || loading}
          className="rounded-lg bg-indigo-600 px-4 py-3 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}
