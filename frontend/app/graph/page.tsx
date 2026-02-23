"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  Search,
  Filter,
  X,
  Users,
  Sparkles,
  MapPin,
  Swords,
  Network,
  Loader2,
} from "lucide-react";
import {
  getSubgraph,
  searchEntities,
  listBooks,
  getCharacterProfile,
} from "@/lib/api";
import type {
  SubgraphData,
  GraphNode,
  BookInfo,
  CharacterProfile,
} from "@/lib/api";
import ForceGraph from "@/components/graph/ForceGraph";
import { cn, labelColor, LABEL_COLORS } from "@/lib/utils";

function GraphExplorerContent() {
  const searchParams = useSearchParams();
  const initialBookId = searchParams.get("book_id") ?? "";
  const initialLabel = searchParams.get("label") ?? "";

  const [books, setBooks] = useState<BookInfo[]>([]);
  const [bookId, setBookId] = useState(initialBookId);
  const [labelFilter, setLabelFilter] = useState(initialLabel);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<GraphNode[]>([]);
  const [graphData, setGraphData] = useState<SubgraphData>({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [charProfile, setCharProfile] = useState<CharacterProfile | null>(null);

  useEffect(() => {
    listBooks().then(setBooks).catch(() => {});
  }, []);

  const loadGraph = useCallback(async () => {
    if (!bookId) return;
    setLoading(true);
    try {
      const data = await getSubgraph(bookId, labelFilter || undefined);
      setGraphData(data);
    } catch {
      setGraphData({ nodes: [], edges: [] });
    } finally {
      setLoading(false);
    }
  }, [bookId, labelFilter]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    try {
      const results = await searchEntities(
        searchQuery,
        labelFilter || undefined,
        bookId || undefined
      );
      setSearchResults(results);
    } catch {
      setSearchResults([]);
    }
  }

  function handleNodeClick(node: GraphNode) {
    setSelectedNode(node);
    setCharProfile(null);
    // Auto-fetch character profile
    if (node.labels?.includes("Character") && node.name) {
      getCharacterProfile(node.name, bookId || undefined)
        .then(setCharProfile)
        .catch(() => {});
    }
  }

  const LABEL_ICONS: Record<string, typeof Users> = {
    Character: Users,
    Skill: Sparkles,
    Location: MapPin,
    Event: Swords,
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Graph Explorer</h1>
          <p className="text-slate-400 text-sm mt-1">
            Visualize and explore the Knowledge Graph
          </p>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap gap-3 items-center">
        {/* Book selector */}
        <select
          value={bookId}
          onChange={(e) => setBookId(e.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
        >
          <option value="">All books</option>
          {books.map((b) => (
            <option key={b.id} value={b.id}>
              {b.title}
            </option>
          ))}
        </select>

        {/* Label filter */}
        <select
          value={labelFilter}
          onChange={(e) => setLabelFilter(e.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
        >
          <option value="">All types</option>
          {Object.keys(LABEL_COLORS).map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>

        {/* Search */}
        <form onSubmit={handleSearch} className="flex gap-2 flex-1 max-w-md">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search entities..."
              className="w-full rounded-lg border border-slate-700 bg-slate-800 pl-9 pr-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
            />
          </div>
          <button
            type="submit"
            className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-500 transition-colors"
          >
            <Search className="h-4 w-4" />
          </button>
        </form>

        {loading && <Loader2 className="h-5 w-5 animate-spin text-indigo-400" />}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-2">
        {Object.entries(LABEL_COLORS).map(([label, color]) => (
          <button
            key={label}
            onClick={() =>
              setLabelFilter(labelFilter === label ? "" : label)
            }
            className={cn(
              "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs border transition-colors",
              labelFilter === label
                ? "border-white/30 bg-white/10"
                : "border-slate-700 bg-slate-800/50 hover:bg-slate-800"
            )}
          >
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: color }}
            />
            {label}
          </button>
        ))}
      </div>

      <div className="flex gap-4">
        {/* Graph */}
        <div className="flex-1 min-w-0">
          <ForceGraph
            data={graphData}
            onNodeClick={handleNodeClick}
            width={selectedNode ? 700 : 1000}
            height={650}
          />
        </div>

        {/* Side panel */}
        {(selectedNode || searchResults.length > 0) && (
          <div className="w-80 shrink-0 space-y-4">
            {/* Search results */}
            {searchResults.length > 0 && (
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 max-h-60 overflow-y-auto">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-medium text-slate-400">
                    Search Results ({searchResults.length})
                  </h3>
                  <button onClick={() => setSearchResults([])}>
                    <X className="h-3.5 w-3.5 text-slate-500" />
                  </button>
                </div>
                <div className="space-y-1">
                  {searchResults.map((r) => (
                    <button
                      key={r.id}
                      onClick={() => handleNodeClick(r)}
                      className="w-full text-left rounded-lg px-2 py-1.5 text-xs hover:bg-slate-800 transition-colors flex items-center gap-2"
                    >
                      <span
                        className="h-2 w-2 rounded-full shrink-0"
                        style={{ backgroundColor: labelColor(r.labels?.[0] ?? "") }}
                      />
                      <span className="truncate font-medium">{r.name}</span>
                      <span className="text-slate-600 ml-auto text-[10px]">
                        {r.labels?.[0]}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Node detail */}
            {selectedNode && (
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span
                      className="h-3 w-3 rounded-full"
                      style={{
                        backgroundColor: labelColor(
                          selectedNode.labels?.[0] ?? ""
                        ),
                      }}
                    />
                    <h3 className="font-semibold text-sm">
                      {selectedNode.name}
                    </h3>
                  </div>
                  <button onClick={() => { setSelectedNode(null); setCharProfile(null); }}>
                    <X className="h-3.5 w-3.5 text-slate-500" />
                  </button>
                </div>
                <div className="text-[10px] font-medium text-slate-500 mb-2">
                  {selectedNode.labels?.join(", ")}
                </div>
                {selectedNode.description && (
                  <p className="text-xs text-slate-400 leading-relaxed mb-3">
                    {selectedNode.description}
                  </p>
                )}

                {/* Character profile details */}
                {charProfile && (
                  <div className="space-y-3 border-t border-slate-800 pt-3">
                    {charProfile.skills.length > 0 && (
                      <DetailSection title="Skills" icon={<Sparkles className="h-3 w-3" />}>
                        {charProfile.skills.map((s) => (
                          <div key={s.name} className="text-xs text-slate-400">
                            <span className="font-medium text-emerald-400">{s.name}</span>
                            {s.rank && <span className="text-slate-600"> ({s.rank})</span>}
                          </div>
                        ))}
                      </DetailSection>
                    )}

                    {charProfile.classes.length > 0 && (
                      <DetailSection title="Classes" icon={<Filter className="h-3 w-3" />}>
                        {charProfile.classes.map((c) => (
                          <div key={c.name} className="text-xs text-slate-400">
                            <span className="font-medium text-amber-400">{c.name}</span>
                            {c.tier && <span className="text-slate-600"> (T{c.tier})</span>}
                          </div>
                        ))}
                      </DetailSection>
                    )}

                    {charProfile.relationships.length > 0 && (
                      <DetailSection title="Relationships" icon={<Users className="h-3 w-3" />}>
                        {charProfile.relationships.map((r, i) => (
                          <div key={i} className="text-xs text-slate-400">
                            <span className="font-medium text-indigo-400">{r.name}</span>
                            <span className="text-slate-600"> ({r.rel_type})</span>
                          </div>
                        ))}
                      </DetailSection>
                    )}

                    {charProfile.events.length > 0 && (
                      <DetailSection title="Events" icon={<Swords className="h-3 w-3" />}>
                        {charProfile.events.slice(0, 5).map((e) => (
                          <div key={e.name} className="text-xs text-slate-400">
                            <span className="font-medium text-red-400">{e.name}</span>
                            <span className="text-slate-600"> (ch.{e.chapter})</span>
                          </div>
                        ))}
                      </DetailSection>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function DetailSection({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-1.5 text-[10px] font-medium text-slate-500 uppercase tracking-wider mb-1">
        {icon} {title}
      </div>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

export default function GraphPage() {
  return (
    <Suspense fallback={<div className="text-slate-500 p-8">Loading...</div>}>
      <GraphExplorerContent />
    </Suspense>
  );
}
