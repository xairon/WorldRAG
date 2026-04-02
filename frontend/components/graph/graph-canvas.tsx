"use client"

import { useEffect, useRef } from "react"
import type { MultiDirectedGraph } from "graphology"
import Sigma from "sigma"
import Forceatlas2Layout from "graphology-layout-forceatlas2/worker"
import { getEntityHex, ENTITY_HEX_FALLBACK } from "@/lib/constants"

interface GraphCanvasProps {
  graph: MultiDirectedGraph | null
  selectedNodeId: string | null
  onNodeClick: (nodeId: string) => void
  onNodeDoubleClick: (nodeId: string) => void
  onCanvasClick: () => void
  zoomRef?: React.MutableRefObject<{
    zoomIn: () => void
    zoomOut: () => void
    fit: () => void
    focusNode: (nodeId: string) => void
  } | null>
  className?: string
}

const LABEL_ZOOM_THRESHOLD = 0.4
const LAYOUT_MAX_MS = 5000
const LAYOUT_CHECK_INTERVAL = 500

export function GraphCanvas({
  graph,
  selectedNodeId,
  onNodeClick,
  onNodeDoubleClick,
  onCanvasClick,
  zoomRef,
  className,
}: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const sigmaRef = useRef<Sigma | null>(null)
  const layoutRef = useRef<Forceatlas2Layout | null>(null)
  const hoveredRef = useRef<string | null>(null)
  const cameraRatioRef = useRef(1)
  // Pre-computed color map for performance (built once per graph change)
  const colorMapRef = useRef<Map<string, string>>(new Map())

  // Build color map from graph node attributes
  useEffect(() => {
    if (!graph) return
    const map = new Map<string, string>()
    graph.forEachNode((id, attrs) => {
      const label = (attrs.entityType as string) ?? "Concept"
      if (!map.has(label)) {
        map.set(label, getEntityHex(label))
      }
    })
    colorMapRef.current = map
  }, [graph])

  // Initialize Sigma + layout
  useEffect(() => {
    if (!containerRef.current || !graph) return

    // Clean up previous instance
    sigmaRef.current?.kill()
    layoutRef.current?.kill()

    // Resolve theme colors once (not per frame)
    const el = containerRef.current
    const edgeColor =
      getComputedStyle(el).getPropertyValue("--muted-foreground").trim() ||
      "#71717a"

    const sigma = new Sigma(graph, el, {
      renderLabels: true,
      labelColor: {
        color:
          getComputedStyle(el).getPropertyValue("--foreground").trim() ||
          "#fafafa",
      },
      labelFont: "Inter, system-ui, sans-serif",
      labelSize: 12,
      defaultEdgeColor: edgeColor,
      defaultNodeColor: ENTITY_HEX_FALLBACK,
      // Node reducer: color by type, size by degree, label visibility
      nodeReducer: (node, data) => {
        const res = { ...data }
        const entityType = graph.getNodeAttribute(node, "entityType") as string
        res.color = colorMapRef.current.get(entityType) ?? ENTITY_HEX_FALLBACK
        const hovered = hoveredRef.current
        const selected = selectedNodeId

        if (hovered && hovered !== node && !graph.areNeighbors(hovered, node)) {
          res.color = `${res.color}33` // dim non-neighbors
          res.label = ""
        }
        if (node === selected) {
          res.highlighted = true
        }
        // Label visibility based on zoom
        if (
          cameraRatioRef.current > LABEL_ZOOM_THRESHOLD &&
          node !== hovered &&
          node !== selected
        ) {
          res.label = ""
        }
        return res
      },
      // Edge reducer: dim when hovering/selecting
      edgeReducer: (edge, data) => {
        const res = { ...data }
        const hovered = hoveredRef.current
        if (hovered) {
          const src = graph.source(edge)
          const tgt = graph.target(edge)
          if (src !== hovered && tgt !== hovered) {
            res.hidden = true
          }
        }
        return res
      },
    })

    sigmaRef.current = sigma

    // Track camera ratio for label visibility
    sigma.getCamera().on("updated", () => {
      cameraRatioRef.current = sigma.getCamera().getState().ratio
    })

    // Hover events
    sigma.on("enterNode", ({ node }) => {
      hoveredRef.current = node
      sigma.refresh()
    })
    sigma.on("leaveNode", () => {
      hoveredRef.current = null
      sigma.refresh()
    })

    // Click events
    sigma.on("clickNode", ({ node }) => onNodeClick(node))
    sigma.on("doubleClickNode", ({ node }) => {
      // Prevent default zoom on double-click
      onNodeDoubleClick(node)
    })
    sigma.on("clickStage", () => onCanvasClick())

    // ForceAtlas2 layout with auto-stop
    const layout = new Forceatlas2Layout(graph, {
      settings: {
        gravity: 0.05,
        scalingRatio: 2,
        barnesHutOptimize: graph.order > 500,
        slowDown: 5,
      },
    })
    layoutRef.current = layout
    layout.start()

    // Auto-stop after convergence or max time
    const startTime = Date.now()
    const checkInterval = setInterval(() => {
      if (Date.now() - startTime > LAYOUT_MAX_MS) {
        layout.stop()
        clearInterval(checkInterval)
      }
    }, LAYOUT_CHECK_INTERVAL)

    // Expose imperative methods
    if (zoomRef) {
      zoomRef.current = {
        zoomIn: () => {
          const camera = sigma.getCamera()
          camera.animatedZoom({ duration: 200 })
        },
        zoomOut: () => {
          const camera = sigma.getCamera()
          camera.animatedUnzoom({ duration: 200 })
        },
        fit: () => {
          const camera = sigma.getCamera()
          camera.animatedReset({ duration: 300 })
        },
        focusNode: (nodeId: string) => {
          const attrs = graph.getNodeAttributes(nodeId)
          if (attrs) {
            sigma.getCamera().animate(
              { x: attrs.x as number, y: attrs.y as number, ratio: 0.3 },
              { duration: 500 },
            )
          }
        },
      }
    }

    return () => {
      clearInterval(checkInterval)
      layout.kill()
      sigma.kill()
      sigmaRef.current = null
      layoutRef.current = null
    }
  }, [graph, onNodeClick, onNodeDoubleClick, onCanvasClick, selectedNodeId])

  // Update highlight when selectedNodeId changes (without rebuilding sigma)
  useEffect(() => {
    sigmaRef.current?.refresh()
  }, [selectedNodeId])

  return (
    <div
      ref={containerRef}
      className={className}
      style={{ width: "100%", height: "100%" }}
      aria-label="Knowledge graph visualization"
    />
  )
}
