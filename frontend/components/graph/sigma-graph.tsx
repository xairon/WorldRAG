"use client"

import { useEffect, useRef, useCallback } from "react"
import Graph from "graphology"
import Sigma from "sigma"
import Forceatlas2Layout from "graphology-layout-forceatlas2/worker"
import { labelColor, LABEL_COLORS } from "@/lib/utils"
import type { SubgraphData } from "@/lib/api/types"

interface SigmaGraphProps {
  data: SubgraphData
  onNodeClick?: (nodeId: string, name: string, labels: string[]) => void
  onNodeHover?: (nodeId: string | null) => void
  onReady?: (actions: { zoomIn: () => void; zoomOut: () => void; resetZoom: () => void }) => void
  highlightNodeId?: string | null
  height?: number | string
  className?: string
}

/**
 * Reads a CSS custom property from the container element or falls back to a default value.
 */
function getCssVar(el: HTMLElement, varName: string, fallback: string): string {
  const value = getComputedStyle(el).getPropertyValue(varName).trim()
  return value || fallback
}

/** Convert any CSS color to rgba with a given alpha using an offscreen canvas. */
function colorWithAlpha(color: string, alpha: number): string {
  if (typeof document === "undefined") return color
  const ctx = document.createElement("canvas").getContext("2d")
  if (!ctx) return color
  ctx.fillStyle = color
  // ctx.fillStyle normalizes to rgb()/rgba() string
  const normalized = ctx.fillStyle
  if (normalized.startsWith("#")) {
    const r = parseInt(normalized.slice(1, 3), 16)
    const g = parseInt(normalized.slice(3, 5), 16)
    const b = parseInt(normalized.slice(5, 7), 16)
    return `rgba(${r},${g},${b},${alpha})`
  }
  // Already rgb(...) form
  return normalized.replace("rgb(", "rgba(").replace(")", `,${alpha})`)
}

export function SigmaGraph({
  data,
  onNodeClick,
  onNodeHover,
  onReady,
  highlightNodeId,
  height = "100%",
  className,
}: SigmaGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const sigmaRef = useRef<Sigma | null>(null)
  const graphRef = useRef<Graph | null>(null)
  const layoutRef = useRef<Forceatlas2Layout | null>(null)
  const hoveredNodeRef = useRef<string | null>(null)

  // Build graphology graph from API data
  const buildGraph = useCallback((data: SubgraphData, edgeColor: string): Graph => {
    const graph = new Graph()

    for (const node of data.nodes) {
      const label = node.labels?.[0] ?? "Concept"
      const degree = data.edges.filter(
        (e) => e.source === node.id || e.target === node.id,
      ).length

      graph.addNode(node.id, {
        label: node.name,
        x: Math.random() * 100,
        y: Math.random() * 100,
        size: Math.max(4, Math.min(20, 4 + degree * 1.5)),
        color: labelColor(label),
        type: "circle",
        // Store metadata for events
        entityType: label,
        entityName: node.name,
        entityLabels: node.labels ?? [],
        description: node.description ?? "",
      })
    }

    for (const edge of data.edges) {
      if (graph.hasNode(edge.source) && graph.hasNode(edge.target)) {
        const edgeKey = `${edge.source}-${edge.target}-${edge.type}`
        if (!graph.hasEdge(edgeKey)) {
          graph.addEdgeWithKey(edgeKey, edge.source, edge.target, {
            label: edge.type,
            size: 1,
            color: edgeColor,
            type: "arrow",
          })
        }
      }
    }

    return graph
  }, [])

  // Initialize/update sigma
  useEffect(() => {
    if (!containerRef.current) return
    if (data.nodes.length === 0) {
      // Clear if no data
      if (sigmaRef.current) {
        sigmaRef.current.kill()
        sigmaRef.current = null
      }
      if (layoutRef.current) {
        layoutRef.current.kill()
        layoutRef.current = null
      }
      return
    }

    const container = containerRef.current

    // Resolve theme-aware colors from CSS variables
    const labelColorResolved = getCssVar(container, "--foreground", "#888888")
    const highlightEdgeColor = getCssVar(container, "--primary", "#a78bfa")
    const mutedColor = getCssVar(container, "--muted-foreground", "#888888")
    const edgeColor = colorWithAlpha(mutedColor, 0.2)
    const dimmedNodeColor = colorWithAlpha(mutedColor, 0.15)

    const graph = buildGraph(data, edgeColor)
    graphRef.current = graph

    // Kill previous instances
    if (layoutRef.current) {
      layoutRef.current.kill()
      layoutRef.current = null
    }
    if (sigmaRef.current) {
      sigmaRef.current.kill()
      sigmaRef.current = null
    }

    // Create sigma renderer
    const sigma = new Sigma(graph, container, {
      renderLabels: true,
      renderEdgeLabels: false,
      labelSize: 12,
      labelWeight: "bold",
      labelColor: { color: labelColorResolved },
      labelFont: "system-ui, sans-serif",
      stagePadding: 30,
      defaultEdgeType: "arrow",
      edgeLabelSize: 9,
      minCameraRatio: 0.1,
      maxCameraRatio: 10,
      // Node reducer for hover highlighting
      nodeReducer: (node, data) => {
        const res = { ...data }
        const hovered = hoveredNodeRef.current

        if (hovered && hovered !== node) {
          // Check if this node is a neighbor of hovered
          const isNeighbor = graph.hasEdge(hovered, node) || graph.hasEdge(node, hovered)
          if (!isNeighbor) {
            res.color = dimmedNodeColor
            res.label = ""
            res.zIndex = 0
          }
        }

        if (hovered === node) {
          res.highlighted = true
          res.zIndex = 1
        }

        return res
      },
      edgeReducer: (edge, data) => {
        const res = { ...data }
        const hovered = hoveredNodeRef.current

        if (hovered) {
          const source = graph.source(edge)
          const target = graph.target(edge)
          if (source !== hovered && target !== hovered) {
            res.hidden = true
          } else {
            res.color = highlightEdgeColor
            res.size = 2
          }
        }

        return res
      },
    })

    sigmaRef.current = sigma

    // Expose zoom actions to parent
    onReady?.({
      zoomIn: () => sigma.getCamera().animatedZoom({ duration: 300 }),
      zoomOut: () => sigma.getCamera().animatedUnzoom({ duration: 300 }),
      resetZoom: () => sigma.getCamera().animatedReset({ duration: 300 }),
    })

    // Start ForceAtlas2 layout
    const layout = new Forceatlas2Layout(graph, {
      settings: {
        gravity: 1,
        scalingRatio: 10,
        strongGravityMode: true,
        slowDown: 5,
        barnesHutOptimize: graph.order > 100,
        barnesHutTheta: 0.5,
      },
    })
    layout.start()
    layoutRef.current = layout

    // Stop layout after convergence
    const layoutTimer = setTimeout(() => {
      if (layoutRef.current) {
        layoutRef.current.stop()
      }
    }, 3000)

    // Event handlers
    sigma.on("clickNode", ({ node }) => {
      const attrs = graph.getNodeAttributes(node)
      onNodeClick?.(node, attrs.entityName, attrs.entityLabels)
    })

    sigma.on("enterNode", ({ node }) => {
      hoveredNodeRef.current = node
      onNodeHover?.(node)
      sigma.refresh()
      if (containerRef.current) {
        containerRef.current.style.cursor = "pointer"
      }
    })

    sigma.on("leaveNode", () => {
      hoveredNodeRef.current = null
      onNodeHover?.(null)
      sigma.refresh()
      if (containerRef.current) {
        containerRef.current.style.cursor = "default"
      }
    })

    return () => {
      clearTimeout(layoutTimer)
      if (layoutRef.current) {
        layoutRef.current.kill()
        layoutRef.current = null
      }
      sigma.kill()
      sigmaRef.current = null
    }
  }, [data, buildGraph, onNodeClick, onNodeHover, onReady])

  // Handle highlight from external source (e.g., search)
  useEffect(() => {
    if (!sigmaRef.current || !graphRef.current || !highlightNodeId) return
    if (!graphRef.current.hasNode(highlightNodeId)) return

    const camera = sigmaRef.current.getCamera()
    const nodePosition = sigmaRef.current.getNodeDisplayData(highlightNodeId)
    if (nodePosition) {
      camera.animate({ x: nodePosition.x, y: nodePosition.y, ratio: 0.3 }, { duration: 500 })
    }
  }, [highlightNodeId])

  return (
    <div
      ref={containerRef}
      className={className}
      style={{
        height,
        width: "100%",
        borderRadius: 0,
        background: "transparent",
        overflow: "hidden",
      }}
    />
  )
}
