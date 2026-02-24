"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Loader2, Info } from "lucide-react";
import { listBooks } from "@/lib/api";
import type { BookInfo } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
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
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    listBooks().then(setBooks).catch((err) => console.error("Failed to load books:", err));
  }, []);

  // Cleanup timeout on unmount
  useEffect(() => () => clearTimeout(timerRef.current), []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    // Placeholder: in the future this will call the RAG query API
    // For now, show a helpful message about the feature
    timerRef.current = setTimeout(() => {
      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: getPlaceholderResponse(userMsg.content, bookId),
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setLoading(false);
    }, 800);
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
          <div
            key={msg.id}
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
              {msg.content}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-800 border border-slate-700">
              <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
            </div>
            <div className="rounded-xl bg-slate-800/50 border border-slate-700 px-4 py-3 text-sm text-slate-500">
              Thinking...
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

/** Placeholder response until the RAG query pipeline is built (Phase 3). */
function getPlaceholderResponse(query: string, bookId: string): string {
  if (!bookId) {
    return "Please select a book first to get answers grounded in the Knowledge Graph.";
  }

  const lower = query.toLowerCase();

  if (lower.includes("character") || lower.includes("who")) {
    return (
      "The RAG query pipeline (Phase 3) is not yet connected. " +
      "Once implemented, this will query the Neo4j Knowledge Graph to find characters " +
      "matching your query, along with their skills, classes, and relationships. " +
      "For now, use the Graph Explorer to browse characters visually!"
    );
  }

  if (lower.includes("skill") || lower.includes("class") || lower.includes("level")) {
    return (
      "Great question about the progression system! " +
      "The Chat interface will use hybrid retrieval (vector + graph) to find " +
      "skills, classes, and level-ups from the KG. " +
      "Try the Graph Explorer to see the current data."
    );
  }

  if (lower.includes("event") || lower.includes("what happened") || lower.includes("battle")) {
    return (
      "Event queries will be powered by the timeline data in the Knowledge Graph. " +
      "The RAG pipeline will combine event nodes, participant links, and source text " +
      "to give you a grounded answer with chapter references."
    );
  }

  return (
    "The RAG query pipeline (Phase 3) is coming soon! It will use:\n" +
    "1. Vector search (Voyage AI embeddings) for semantic matching\n" +
    "2. Graph traversal (Neo4j) for structured relationships\n" +
    "3. Reranking (Cohere) for relevance scoring\n" +
    "4. LLM generation (GPT-4o) for natural language answers\n\n" +
    "In the meantime, explore the Knowledge Graph visually using the Graph Explorer!"
  );
}
