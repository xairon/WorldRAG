"use client"

import { useEffect, useState, useCallback } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import {
  ArrowLeft,
  Loader2,
  Zap,
  BookOpen,
  FileCode,
  Regex,
  GitBranch,
  Workflow,
  Database,
  Boxes,
} from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { getBook, extractBook } from "@/lib/api/books"
import { getPipelineConfig } from "@/lib/api/pipeline"
import type { BookDetail } from "@/lib/api/types"
import type { PipelineConfig } from "@/lib/api/pipeline"
import { cn, statusColor } from "@/lib/utils"
import { useExtractionProgress } from "@/hooks/use-extraction-progress"
import { ExtractionProgress } from "@/components/shared/extraction-progress"
import { ChapterSelector } from "@/components/pipeline/chapter-selector"
import { PromptViewer } from "@/components/pipeline/prompt-viewer"
import { RegexViewer } from "@/components/pipeline/regex-viewer"
import { OntologyTree } from "@/components/pipeline/ontology-tree"
import { GraphTopology } from "@/components/pipeline/graph-topology"
import { SchemaViewer } from "@/components/pipeline/schema-viewer"
import { ModelViewer } from "@/components/pipeline/model-viewer"

export default function PipelineBookPage() {
  const params = useParams()
  const bookId = params.id as string

  const [detail, setDetail] = useState<BookDetail | null>(null)
  const [config, setConfig] = useState<PipelineConfig | null>(null)
  const [selectedChapters, setSelectedChapters] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(true)
  const [extracting, setExtracting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const extraction = useExtractionProgress()

  const refreshData = useCallback(async () => {
    try {
      const d = await getBook(bookId)
      setDetail(d)
    } catch {
      /* ignore refresh errors */
    }
  }, [bookId])

  useEffect(() => {
    async function load() {
      try {
        const [d, c] = await Promise.allSettled([
          getBook(bookId),
          getPipelineConfig(),
        ])
        if (d.status === "fulfilled") {
          setDetail(d.value)
          if (d.value.book.status === "extracting") {
            setExtracting(true)
            extraction.connect(bookId)
          }
        } else {
          setError("Book not found")
        }
        if (c.status === "fulfilled") setConfig(c.value)
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load")
      } finally {
        setLoading(false)
      }
    }
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bookId])

  useEffect(() => {
    if (extraction.isDone) {
      setExtracting(false)
      refreshData()
    }
  }, [extraction.isDone, refreshData])

  const handleExtract = useCallback(async () => {
    if (selectedChapters.size === 0) return
    setError(null)
    try {
      const chapters = Array.from(selectedChapters).sort((a, b) => a - b)
      await extractBook(bookId, { chapters })
      setExtracting(true)
      extraction.connect(bookId)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Extraction failed")
    }
  }, [bookId, selectedChapters, extraction])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-pulse text-slate-500">Loading pipeline...</div>
      </div>
    )
  }

  if (!detail) {
    return (
      <div className="text-center py-20">
        <p className="text-red-400 mb-4">{error ?? "Book not found"}</p>
        <Link href="/library" className="text-indigo-400 hover:underline">
          Back to library
        </Link>
      </div>
    )
  }

  const { book, chapters } = detail

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <Link
            href={`/library/${bookId}`}
            className="text-sm text-slate-500 hover:text-slate-300 flex items-center gap-1 mb-2"
          >
            <ArrowLeft className="h-3 w-3" /> Back to book
          </Link>
          <h1 className="text-2xl font-bold tracking-tight">
            Pipeline — {book.title}
          </h1>
          <div className="flex items-center gap-3 mt-2 text-sm text-slate-400">
            {book.author && <span>by {book.author}</span>}
            <span
              className={cn(
                "text-[10px] font-medium px-2 py-0.5 rounded-full border",
                statusColor(book.status),
              )}
            >
              {book.status}
            </span>
            <span className="text-slate-600">
              {book.total_chapters} chapters
            </span>
          </div>
        </div>
      </div>

      {/* Extraction progress */}
      {extracting && (
        <Card>
          <CardContent className="pt-5 pb-4">
            <div className="flex items-center gap-2 mb-3">
              <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
              <h2 className="text-sm font-medium text-slate-400">
                Extraction in Progress
              </h2>
            </div>
            <ExtractionProgress
              events={extraction.events}
              progress={extraction.progress}
              isConnected={extraction.isConnected}
              isDone={extraction.isDone}
              isStarted={extraction.isStarted}
              totalChapters={extraction.totalChapters}
            />
          </CardContent>
        </Card>
      )}

      {error && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-4 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultValue="chapters">
        <TabsList className="w-full justify-start">
          <TabsTrigger value="chapters" className="gap-1.5">
            <BookOpen className="h-3.5 w-3.5" />
            Chapters
          </TabsTrigger>
          <TabsTrigger value="prompts" className="gap-1.5">
            <FileCode className="h-3.5 w-3.5" />
            Prompts
          </TabsTrigger>
          <TabsTrigger value="regex" className="gap-1.5">
            <Regex className="h-3.5 w-3.5" />
            Regex
          </TabsTrigger>
          <TabsTrigger value="ontology" className="gap-1.5">
            <GitBranch className="h-3.5 w-3.5" />
            Ontology
          </TabsTrigger>
          <TabsTrigger value="pipeline" className="gap-1.5">
            <Workflow className="h-3.5 w-3.5" />
            Pipeline
          </TabsTrigger>
          <TabsTrigger value="schema" className="gap-1.5">
            <Database className="h-3.5 w-3.5" />
            Schema
          </TabsTrigger>
          <TabsTrigger value="models" className="gap-1.5">
            <Boxes className="h-3.5 w-3.5" />
            Models
          </TabsTrigger>
        </TabsList>

        {/* Chapters tab */}
        <TabsContent value="chapters">
          <Card>
            <CardContent className="pt-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-medium text-slate-400">
                  Select chapters for extraction
                </h2>
                <Button
                  onClick={handleExtract}
                  disabled={selectedChapters.size === 0 || extracting}
                  size="sm"
                >
                  <Zap className="h-4 w-4 mr-2" />
                  Extract {selectedChapters.size > 0 && (
                    <Badge variant="secondary" className="ml-1.5 text-[10px]">
                      {selectedChapters.size}
                    </Badge>
                  )}
                </Button>
              </div>
              <ChapterSelector
                chapters={chapters}
                selected={selectedChapters}
                onSelectionChange={setSelectedChapters}
                disabled={extracting}
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Prompts tab */}
        <TabsContent value="prompts">
          <Card>
            <CardContent className="pt-5">
              {config ? (
                <PromptViewer prompts={config.prompts} />
              ) : (
                <LoadingPlaceholder />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Regex tab */}
        <TabsContent value="regex">
          <Card>
            <CardContent className="pt-5">
              {config ? (
                <RegexViewer patterns={config.regex_patterns} />
              ) : (
                <LoadingPlaceholder />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Ontology tab */}
        <TabsContent value="ontology">
          <Card>
            <CardContent className="pt-5">
              {config ? (
                <OntologyTree
                  nodeTypes={config.ontology_node_types}
                  relTypes={config.ontology_rel_types}
                />
              ) : (
                <LoadingPlaceholder />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Pipeline graph tab */}
        <TabsContent value="pipeline">
          <Card>
            <CardContent className="pt-5">
              {config ? (
                <GraphTopology graph={config.extraction_graph} />
              ) : (
                <LoadingPlaceholder />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Schema tab */}
        <TabsContent value="schema">
          <Card>
            <CardContent className="pt-5">
              {config ? (
                <SchemaViewer schema={config.neo4j_schema} />
              ) : (
                <LoadingPlaceholder />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Models tab */}
        <TabsContent value="models">
          <Card>
            <CardContent className="pt-5">
              {config ? (
                <ModelViewer models={config.extraction_models} />
              ) : (
                <LoadingPlaceholder />
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

function LoadingPlaceholder() {
  return (
    <div className="flex items-center justify-center h-40">
      <div className="animate-pulse text-slate-500 text-sm">
        Loading pipeline config...
      </div>
    </div>
  )
}
