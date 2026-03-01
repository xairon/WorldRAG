"use client"

import { cn } from "@/lib/utils"
import type { ExtractionGraphInfo } from "@/lib/api/pipeline"

interface GraphTopologyProps {
  graph: ExtractionGraphInfo
}

const NODE_COLORS: Record<string, string> = {
  route: "border-amber-500/50 bg-amber-500/10 text-amber-300",
  pass: "border-indigo-500/50 bg-indigo-500/10 text-indigo-300",
  merge: "border-cyan-500/50 bg-cyan-500/10 text-cyan-300",
  postprocess: "border-emerald-500/50 bg-emerald-500/10 text-emerald-300",
}

const NODE_TYPE_LABELS: Record<string, string> = {
  route: "Router",
  pass: "Extraction Pass",
  merge: "Merge",
  postprocess: "Post-process",
}

export function GraphTopology({ graph }: GraphTopologyProps) {
  const nodeMap = Object.fromEntries(graph.nodes.map((n) => [n.name, n]))

  // Group by stage
  const router = graph.nodes.filter((n) => n.node_type === "route")
  const passes = graph.nodes.filter((n) => n.node_type === "pass")
  const merge = graph.nodes.filter((n) => n.node_type === "merge")
  const post = graph.nodes.filter((n) => n.node_type === "postprocess")

  return (
    <div className="space-y-8">
      {/* Legend */}
      <div className="flex flex-wrap gap-4">
        {Object.entries(NODE_COLORS).map(([type, cls]) => (
          <div key={type} className="flex items-center gap-2">
            <div className={cn("w-3 h-3 rounded border", cls)} />
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
              {NODE_TYPE_LABELS[type]}
            </span>
          </div>
        ))}
      </div>

      {/* Flow diagram */}
      <div className="flex flex-col items-center gap-4">
        {/* START */}
        <div className="px-4 py-1.5 rounded-full border border-[var(--glass-border)] bg-accent text-xs text-muted-foreground">
          START
        </div>
        <Arrow />

        {/* Router */}
        {router.map((n) => (
          <NodeCard key={n.name} node={n} />
        ))}
        <Arrow label="conditional fan-out" />

        {/* Passes (horizontal) */}
        <div className="flex gap-3 flex-wrap justify-center">
          {passes.map((n) => (
            <NodeCard key={n.name} node={n} />
          ))}
        </div>
        <Arrow label="fan-in" />

        {/* Merge */}
        {merge.map((n) => (
          <NodeCard key={n.name} node={n} />
        ))}
        <Arrow />

        {/* Post-process (horizontal) */}
        <div className="flex gap-3 flex-wrap justify-center">
          {post.map((n) => (
            <NodeCard key={n.name} node={n} />
          ))}
        </div>
        <Arrow />

        {/* END */}
        <div className="px-4 py-1.5 rounded-full border border-[var(--glass-border)] bg-accent text-xs text-muted-foreground">
          END
        </div>
      </div>

      {/* Edge list */}
      <div>
        <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
          Edges ({graph.edges.length})
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
          {graph.edges.map((e, i) => (
            <div
              key={i}
              className="flex items-center gap-2 text-[11px] px-3 py-1.5 rounded bg-background"
            >
              <span className="font-mono text-foreground">{e.source}</span>
              <span className="text-muted-foreground/60">&rarr;</span>
              <span className="font-mono text-foreground">{e.target}</span>
              {e.label && (
                <span className="text-muted-foreground ml-auto">{e.label}</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function NodeCard({ node }: { node: { name: string; description: string; node_type: string } }) {
  const color = NODE_COLORS[node.node_type] ?? "border-[var(--glass-border)] bg-accent text-foreground"
  return (
    <div className={cn("rounded-lg border px-4 py-2.5 min-w-[160px] text-center", color)}>
      <div className="text-xs font-medium">{node.name}</div>
      <div className="text-[10px] opacity-70 mt-0.5">{node.description}</div>
    </div>
  )
}

function Arrow({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <div className="w-px h-4 bg-[var(--glass-border)]" />
      {label && <span className="text-[9px] text-muted-foreground/60">{label}</span>}
      <div className="text-muted-foreground/60 text-xs">&darr;</div>
    </div>
  )
}
