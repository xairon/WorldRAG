"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import type { OntologyEntityType, OntologySchemaEdge } from "@/lib/api/graph"

const LAYER_COLORS: Record<string, string> = {
  core: "#3b82f6",
  genre: "#8b5cf6",
  induced: "#f59e0b",
}

interface Node {
  id: string
  count: number
  layer: string
  x: number
  y: number
  vx: number
  vy: number
  radius: number
}

interface Edge {
  source: string
  target: string
  relation: string
  count: number
}

function buildGraph(entityTypes: OntologyEntityType[], schemaEdges: OntologySchemaEdge[]) {
  // Aggregate schema edges by (source, target) — merge relation types
  const edgeMap = new Map<string, Edge>()
  for (const e of schemaEdges) {
    const key = `${e.source}:${e.target}`
    const existing = edgeMap.get(key)
    if (existing) {
      existing.count += e.count
      if (!existing.relation.includes(e.relation)) {
        const parts = existing.relation.split(", ")
        if (parts.length < 2) existing.relation += `, ${e.relation}`
      }
    } else {
      edgeMap.set(key, { source: e.source, target: e.target, relation: e.relation, count: e.count })
    }
  }

  const nodeSet = new Set(entityTypes.map((e) => e.label))
  const nodes: Node[] = entityTypes.map((e, i) => {
    const angle = (2 * Math.PI * i) / entityTypes.length
    const spread = 250
    return {
      id: e.label,
      count: e.count,
      layer: e.layer,
      x: 400 + Math.cos(angle) * spread + (Math.random() - 0.5) * 40,
      y: 300 + Math.sin(angle) * spread + (Math.random() - 0.5) * 40,
      vx: 0,
      vy: 0,
      radius: Math.max(18, Math.min(45, Math.log(e.count + 1) * 7)),
    }
  })

  const edges = [...edgeMap.values()].filter((e) => nodeSet.has(e.source) && nodeSet.has(e.target) && e.source !== e.target)

  return { nodes, edges }
}

function simulate(nodes: Node[], edges: Edge[], iterations: number) {
  const nodeMap = new Map(nodes.map((n) => [n.id, n]))
  const cx = 400
  const cy = 300

  for (let i = 0; i < iterations; i++) {
    const alpha = 1 - i / iterations

    // Repulsion between all nodes
    for (let a = 0; a < nodes.length; a++) {
      for (let b = a + 1; b < nodes.length; b++) {
        const na = nodes[a]
        const nb = nodes[b]
        let dx = nb.x - na.x
        let dy = nb.y - na.y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const force = (800 * alpha) / (dist * dist)
        dx = (dx / dist) * force
        dy = (dy / dist) * force
        na.vx -= dx
        na.vy -= dy
        nb.vx += dx
        nb.vy += dy
      }
    }

    // Attraction along edges
    for (const e of edges) {
      const src = nodeMap.get(e.source)
      const tgt = nodeMap.get(e.target)
      if (!src || !tgt) continue
      const dx = tgt.x - src.x
      const dy = tgt.y - src.y
      const dist = Math.sqrt(dx * dx + dy * dy) || 1
      const force = (dist - 120) * 0.01 * alpha
      const fx = (dx / dist) * force
      const fy = (dy / dist) * force
      src.vx += fx
      src.vy += fy
      tgt.vx -= fx
      tgt.vy -= fy
    }

    // Center gravity
    for (const n of nodes) {
      n.vx += (cx - n.x) * 0.005 * alpha
      n.vy += (cy - n.y) * 0.005 * alpha
    }

    // Apply velocity with damping
    for (const n of nodes) {
      n.vx *= 0.6
      n.vy *= 0.6
      n.x += n.vx
      n.y += n.vy
    }
  }
}

interface SchemaGraphProps {
  entityTypes: OntologyEntityType[]
  schemaEdges: OntologySchemaEdge[]
}

export function SchemaGraph({ entityTypes, schemaEdges }: SchemaGraphProps) {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const { nodes, edges } = useMemo(() => {
    const g = buildGraph(entityTypes, schemaEdges)
    simulate(g.nodes, g.edges, 200)
    return g
  }, [entityTypes, schemaEdges])

  const nodeMap = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes])

  const connectedToHovered = useMemo(() => {
    if (!hoveredNode) return new Set<string>()
    const s = new Set<string>([hoveredNode])
    for (const e of edges) {
      if (e.source === hoveredNode) s.add(e.target)
      if (e.target === hoveredNode) s.add(e.source)
    }
    return s
  }, [hoveredNode, edges])

  const getNodeOpacity = useCallback(
    (id: string) => {
      if (!hoveredNode) return 1
      return connectedToHovered.has(id) ? 1 : 0.15
    },
    [hoveredNode, connectedToHovered],
  )

  const getEdgeOpacity = useCallback(
    (e: Edge) => {
      if (!hoveredNode) return 0.4
      return e.source === hoveredNode || e.target === hoveredNode ? 0.8 : 0.05
    },
    [hoveredNode],
  )

  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/50">
      <div className="flex items-center gap-4 border-b border-slate-200 px-6 py-3 dark:border-slate-800">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">Ontology Schema</h3>
        <div className="flex gap-3 text-xs text-slate-500">
          <span className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-blue-500" /> Core
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-purple-500" /> Genre
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-amber-500" /> Induced
          </span>
        </div>
      </div>
      <svg
        ref={svgRef}
        viewBox="0 0 800 600"
        className="h-[500px] w-full"
        style={{ background: "transparent" }}
      >
        <defs>
          <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#94a3b8" fillOpacity="0.5" />
          </marker>
          {Object.entries(LAYER_COLORS).map(([layer, color]) => (
            <filter key={layer} id={`glow-${layer}`}>
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feFlood floodColor={color} floodOpacity="0.3" result="color" />
              <feComposite in="color" in2="blur" operator="in" result="shadow" />
              <feMerge>
                <feMergeNode in="shadow" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          ))}
        </defs>

        {/* Edges */}
        {edges.map((e, i) => {
          const src = nodeMap.get(e.source)
          const tgt = nodeMap.get(e.target)
          if (!src || !tgt) return null
          const opacity = getEdgeOpacity(e)
          const mx = (src.x + tgt.x) / 2
          const my = (src.y + tgt.y) / 2
          const strokeWidth = Math.max(1, Math.min(4, Math.log(e.count + 1) * 0.6))
          return (
            <g key={i} style={{ opacity, transition: "opacity 200ms" }}>
              <line
                x1={src.x}
                y1={src.y}
                x2={tgt.x}
                y2={tgt.y}
                stroke="#94a3b8"
                strokeWidth={strokeWidth}
                markerEnd="url(#arrowhead)"
              />
              {opacity > 0.3 && (
                <text
                  x={mx}
                  y={my - 4}
                  textAnchor="middle"
                  className="fill-slate-400 text-[8px] dark:fill-slate-500"
                  style={{ pointerEvents: "none" }}
                >
                  {e.relation.length > 18 ? e.relation.slice(0, 16) + ".." : e.relation}
                </text>
              )}
            </g>
          )
        })}

        {/* Nodes */}
        {nodes.map((n) => {
          const color = LAYER_COLORS[n.layer] || "#64748b"
          const opacity = getNodeOpacity(n.id)
          return (
            <g
              key={n.id}
              style={{ opacity, transition: "opacity 200ms", cursor: "pointer" }}
              onMouseEnter={() => setHoveredNode(n.id)}
              onMouseLeave={() => setHoveredNode(null)}
            >
              <circle
                cx={n.x}
                cy={n.y}
                r={n.radius}
                fill={color}
                fillOpacity={0.15}
                stroke={color}
                strokeWidth={2}
                filter={`url(#glow-${n.layer})`}
              />
              <text
                x={n.x}
                y={n.y + 1}
                textAnchor="middle"
                dominantBaseline="middle"
                className="fill-slate-800 text-[10px] font-bold dark:fill-white"
                style={{ pointerEvents: "none" }}
              >
                {n.count}
              </text>
              <text
                x={n.x}
                y={n.y + n.radius + 12}
                textAnchor="middle"
                className="fill-slate-600 text-[10px] font-medium dark:fill-slate-400"
                style={{ pointerEvents: "none" }}
              >
                {n.id}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
