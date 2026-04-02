"use client"

import { useMemo, useState, useCallback } from "react"
import { motion } from "motion/react"
import { getEntityHex } from "@/lib/constants"
import type { OntologyEntityType, OntologySchemaEdge } from "@/lib/api/graph"

interface SchemaGraphProps {
  entityTypes: OntologyEntityType[]
  schemaEdges: OntologySchemaEdge[]
  selectedType: string | null
  onSelectType: (type: string | null) => void
}

interface LayoutNode {
  id: string
  count: number
  layer: string
  x: number
  y: number
  radius: number
  color: string
}

interface LayoutEdge {
  source: string
  target: string
  relation: string
  count: number
}

const LAYER_RADII = { core: 130, genre: 220, induced: 290 } as const
const CENTER = { x: 400, y: 350 }
const NODE_MIN_R = 18
const NODE_MAX_R = 40

function computeLayout(entityTypes: OntologyEntityType[]): LayoutNode[] {
  const groups: Record<string, OntologyEntityType[]> = { core: [], genre: [], induced: [] }
  for (const et of entityTypes) {
    const layer = et.layer ?? "core"
    ;(groups[layer] ?? groups.core).push(et)
  }

  const maxCount = Math.max(1, ...entityTypes.map((e) => e.count))
  const nodes: LayoutNode[] = []

  for (const [layer, types] of Object.entries(groups)) {
    if (types.length === 0) continue
    const ringRadius = LAYER_RADII[layer as keyof typeof LAYER_RADII] ?? 220
    const angleStep = (2 * Math.PI) / types.length
    const startAngle = -Math.PI / 2 // start from top

    for (let i = 0; i < types.length; i++) {
      const et = types[i]
      const angle = startAngle + i * angleStep
      const nodeRadius =
        NODE_MIN_R + (NODE_MAX_R - NODE_MIN_R) * Math.sqrt(et.count / maxCount)

      nodes.push({
        id: et.label,
        count: et.count,
        layer,
        x: CENTER.x + ringRadius * Math.cos(angle),
        y: CENTER.y + ringRadius * Math.sin(angle),
        radius: nodeRadius,
        color: getEntityHex(et.label),
      })
    }
  }

  return nodes
}

function aggregateEdges(schemaEdges: OntologySchemaEdge[]): LayoutEdge[] {
  const map = new Map<string, LayoutEdge>()
  for (const e of schemaEdges) {
    const key = `${e.source}::${e.target}`
    const existing = map.get(key)
    if (existing) {
      existing.count += e.count
      if (!existing.relation.includes(e.relation)) {
        existing.relation += `, ${e.relation}`
      }
    } else {
      map.set(key, { source: e.source, target: e.target, relation: e.relation, count: e.count })
    }
  }
  return Array.from(map.values())
}

export function SchemaGraph({
  entityTypes,
  schemaEdges,
  selectedType,
  onSelectType,
}: SchemaGraphProps) {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)

  const nodes = useMemo(() => computeLayout(entityTypes), [entityTypes])
  const edges = useMemo(() => aggregateEdges(schemaEdges), [schemaEdges])
  const nodeMap = useMemo(
    () => new Map(nodes.map((n) => [n.id, n])),
    [nodes],
  )

  // Connected nodes for hover/select highlighting
  const connectedTo = useMemo(() => {
    const active = hoveredNode ?? selectedType
    if (!active) return null
    const set = new Set<string>([active])
    for (const e of edges) {
      if (e.source === active) set.add(e.target)
      if (e.target === active) set.add(e.source)
    }
    return set
  }, [hoveredNode, selectedType, edges])

  const getNodeOpacity = useCallback(
    (id: string) => {
      if (!connectedTo) return 1
      return connectedTo.has(id) ? 1 : 0.15
    },
    [connectedTo],
  )

  const getEdgeOpacity = useCallback(
    (source: string, target: string) => {
      const active = hoveredNode ?? selectedType
      if (!active) return 0.4
      return source === active || target === active ? 0.8 : 0.05
    },
    [hoveredNode, selectedType],
  )

  const handleNodeClick = useCallback(
    (id: string) => {
      onSelectType(selectedType === id ? null : id)
    },
    [selectedType, onSelectType],
  )

  return (
    <div className="w-full overflow-hidden rounded-xl border bg-card">
      {/* Legend header */}
      <div className="flex items-center gap-4 px-4 py-2 border-b text-xs">
        <span className="text-muted-foreground font-medium">Layers:</span>
        {[
          { layer: "core", color: "#3b82f6", label: "Core" },
          { layer: "genre", color: "#8b5cf6", label: "Genre" },
          { layer: "induced", color: "#f59e0b", label: "Induced" },
        ].map((l) => (
          <span key={l.layer} className="flex items-center gap-1.5">
            <span
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: l.color }}
            />
            {l.label}
          </span>
        ))}
        {selectedType && (
          <button
            onClick={() => onSelectType(null)}
            className="ml-auto text-xs text-muted-foreground hover:text-foreground"
          >
            Clear filter
          </button>
        )}
      </div>

      <svg
        viewBox="0 0 800 700"
        className="w-full h-auto"
        onClick={(e) => {
          if ((e.target as SVGElement).tagName === "svg") {
            onSelectType(null)
          }
        }}
      >
        <defs>
          {/* Glow filter */}
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          {/* Arrow marker */}
          <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse"
            fill="currentColor" opacity="0.4">
            <path d="M 0 0 L 10 5 L 0 10 z" />
          </marker>
          {/* Edge gradients */}
          {edges.map((edge, i) => {
            const src = nodeMap.get(edge.source)
            const tgt = nodeMap.get(edge.target)
            if (!src || !tgt) return null
            return (
              <linearGradient
                key={`grad-${i}`}
                id={`edge-grad-${i}`}
                x1={src.x} y1={src.y} x2={tgt.x} y2={tgt.y}
                gradientUnits="userSpaceOnUse"
              >
                <stop offset="0%" stopColor={src.color} stopOpacity="0.6" />
                <stop offset="100%" stopColor={tgt.color} stopOpacity="0.6" />
              </linearGradient>
            )
          })}
        </defs>

        {/* Edges */}
        {edges.map((edge, i) => {
          const src = nodeMap.get(edge.source)
          const tgt = nodeMap.get(edge.target)
          if (!src || !tgt) return null

          // Offset edge endpoints to node border
          const dx = tgt.x - src.x
          const dy = tgt.y - src.y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const nx = dx / dist
          const ny = dy / dist

          const x1 = src.x + nx * src.radius
          const y1 = src.y + ny * src.radius
          const x2 = tgt.x - nx * tgt.radius
          const y2 = tgt.y - ny * tgt.radius

          // Midpoint for label
          const mx = (x1 + x2) / 2
          const my = (y1 + y2) / 2

          const opacity = getEdgeOpacity(edge.source, edge.target)
          const label = edge.relation.length > 20
            ? edge.relation.slice(0, 18) + "\u2026"
            : edge.relation

          return (
            <g key={`edge-${i}`} opacity={opacity}>
              <line
                x1={x1} y1={y1} x2={x2} y2={y2}
                stroke={`url(#edge-grad-${i})`}
                strokeWidth={Math.max(1, Math.min(3, Math.log2(edge.count + 1)))}
                markerEnd="url(#arrow)"
              />
              <text
                x={mx} y={my - 4}
                textAnchor="middle"
                className="fill-muted-foreground"
                fontSize="8"
                opacity="0.7"
              >
                {label}
              </text>
            </g>
          )
        })}

        {/* Nodes */}
        {nodes.map((node, i) => {
          const opacity = getNodeOpacity(node.id)
          const isSelected = selectedType === node.id
          const isHovered = hoveredNode === node.id

          return (
            <motion.g
              key={node.id}
              initial={{ opacity: 0, scale: 0.5 }}
              animate={{
                opacity,
                scale: 1,
              }}
              transition={{ delay: i * 0.03, duration: 0.3 }}
              style={{ cursor: "pointer" }}
              onMouseEnter={() => setHoveredNode(node.id)}
              onMouseLeave={() => setHoveredNode(null)}
              onClick={(e) => {
                e.stopPropagation()
                handleNodeClick(node.id)
              }}
            >
              {/* Glow circle */}
              <circle
                cx={node.x} cy={node.y}
                r={node.radius + 4}
                fill={node.color}
                opacity={isSelected || isHovered ? 0.25 : 0}
                filter="url(#glow)"
              />
              {/* Main circle */}
              <circle
                cx={node.x} cy={node.y}
                r={node.radius}
                fill={node.color}
                opacity={0.15}
                stroke={node.color}
                strokeWidth={isSelected ? 3 : 1.5}
                strokeDasharray={node.layer === "induced" ? "4,3" : "none"}
              />
              {/* Label */}
              <text
                x={node.x} y={node.y - 2}
                textAnchor="middle"
                dominantBaseline="middle"
                className="fill-foreground font-medium pointer-events-none"
                fontSize={node.radius > 28 ? "11" : "9"}
              >
                {node.id}
              </text>
              {/* Count */}
              <text
                x={node.x} y={node.y + 12}
                textAnchor="middle"
                dominantBaseline="middle"
                className="fill-muted-foreground pointer-events-none"
                fontSize="8"
              >
                {node.count}
              </text>
            </motion.g>
          )
        })}
      </svg>
    </div>
  )
}
