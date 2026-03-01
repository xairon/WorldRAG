"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import {
  FileCode,
  Regex,
  GitBranch,
  Workflow,
  Database,
  Boxes,
  ArrowRight,
} from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { getPipelineConfig } from "@/lib/api/pipeline"
import { listBooks } from "@/lib/api/books"
import type { PipelineConfig } from "@/lib/api/pipeline"
import type { BookInfo } from "@/lib/api/types"
import { cn, statusColor } from "@/lib/utils"
import { PromptViewer } from "@/components/pipeline/prompt-viewer"
import { RegexViewer } from "@/components/pipeline/regex-viewer"
import { OntologyTree } from "@/components/pipeline/ontology-tree"
import { GraphTopology } from "@/components/pipeline/graph-topology"
import { SchemaViewer } from "@/components/pipeline/schema-viewer"
import { ModelViewer } from "@/components/pipeline/model-viewer"

export default function PipelinePage() {
  const [config, setConfig] = useState<PipelineConfig | null>(null)
  const [books, setBooks] = useState<BookInfo[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      const [c, b] = await Promise.allSettled([
        getPipelineConfig(),
        listBooks(),
      ])
      if (c.status === "fulfilled") setConfig(c.value)
      if (b.status === "fulfilled") setBooks(b.value)
      setLoading(false)
    }
    load()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="animate-pulse text-muted-foreground">
          Loading pipeline config...
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Pipeline Dashboard
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Inspect extraction configuration, prompts, ontology, and data models.
          Select a book to run extraction.
        </p>
      </div>

      {/* Book cards for extraction access */}
      {books.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-muted-foreground mb-3">
            Books — select to extract
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {books.map((b) => (
              <Link
                key={b.id}
                href={`/pipeline/${b.id}`}
                className="group glass rounded-lg p-4 hover:border-primary/40 hover:bg-accent transition-all"
              >
                <div className="flex items-start justify-between">
                  <div className="min-w-0">
                    <h3 className="text-sm font-medium truncate group-hover:text-primary transition-colors">
                      {b.title}
                    </h3>
                    <div className="flex items-center gap-2 mt-1">
                      {b.author && (
                        <span className="text-xs text-muted-foreground truncate">
                          {b.author}
                        </span>
                      )}
                      <span className="text-xs text-muted-foreground/60">
                        {b.total_chapters} ch
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span
                      className={cn(
                        "text-[9px] font-medium px-1.5 py-0.5 rounded-full border",
                        statusColor(b.status),
                      )}
                    >
                      {b.status}
                    </span>
                    <ArrowRight className="h-3.5 w-3.5 text-muted-foreground/60 group-hover:text-primary transition-colors" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Config inspection tabs */}
      <Tabs defaultValue="prompts">
        <TabsList className="w-full justify-start">
          <TabsTrigger value="prompts" className="gap-1.5">
            <FileCode className="h-3.5 w-3.5" />
            Prompts
            {config && (
              <Badge variant="secondary" className="ml-1 text-[9px] h-4">
                {config.prompts.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="regex" className="gap-1.5">
            <Regex className="h-3.5 w-3.5" />
            Regex
            {config && (
              <Badge variant="secondary" className="ml-1 text-[9px] h-4">
                {config.regex_patterns.length}
              </Badge>
            )}
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
            {config && (
              <Badge variant="secondary" className="ml-1 text-[9px] h-4">
                {config.extraction_models.length}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

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
      <div className="animate-pulse text-muted-foreground text-sm">
        Loading pipeline config...
      </div>
    </div>
  )
}
