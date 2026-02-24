"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import type { SubgraphData, GraphNode } from "@/lib/api";
import { labelColor } from "@/lib/utils";

/** Force-graph node with simulation coordinates. */
interface ForceGraphNode extends GraphNode {
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
}

// Dynamic import to avoid SSR issues with canvas
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
}) as React.ComponentType<Record<string, unknown>>;

interface ForceGraphProps {
  data: SubgraphData;
  onNodeClick?: (node: GraphNode) => void;
  height?: number;
}

export default function ForceGraph({
  data,
  onNodeClick,
  height = 650,
}: ForceGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w && w > 0) setWidth(Math.round(w));
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Derive graph data from props (no useEffect + setState)
  const graphData = useMemo(() => {
    if (!data.nodes.length) {
      return { nodes: [] as Record<string, unknown>[], links: [] as Record<string, unknown>[] };
    }

    const nodeIds = new Set(data.nodes.map((n) => n.id));
    const links = data.edges
      .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
      .map((e) => ({ ...e }));

    return {
      nodes: data.nodes.map((n) => ({ ...n })),
      links,
    };
  }, [data]);

  const handleNodeClick = useCallback(
    (node: ForceGraphNode) => {
      if (onNodeClick) {
        onNodeClick(node as GraphNode);
      }
    },
    [onNodeClick]
  );

  const paintNode = useCallback(
    (node: ForceGraphNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const label = node.labels?.[0] ?? "Unknown";
      const color = labelColor(label);
      const fontSize = 12 / globalScale;
      const nodeSize = 6;
      const x = node.x ?? 0;
      const y = node.y ?? 0;

      // Node circle with glow
      ctx.shadowColor = color;
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.arc(x, y, nodeSize, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.shadowBlur = 0;

      // Label
      if (globalScale > 0.8) {
        ctx.font = `${fontSize}px sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillStyle = "#e2e8f0";
        ctx.fillText(node.name ?? "", x, y + nodeSize + 2);
      }
    },
    []
  );

  const paintArea = useCallback(
    (node: ForceGraphNode, color: string, ctx: CanvasRenderingContext2D) => {
      ctx.beginPath();
      ctx.arc(node.x ?? 0, node.y ?? 0, 8, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();
    },
    []
  );

  if (!data.nodes.length) {
    return (
      <div
        ref={containerRef}
        className="flex items-center justify-center border border-slate-800 rounded-xl bg-slate-900/30 w-full"
        style={{ height }}
      >
        <p className="text-slate-500 text-sm">No graph data to display</p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="graph-canvas rounded-xl overflow-hidden border border-slate-800 bg-slate-950 w-full">
      <ForceGraph2D
        width={width}
        height={height}
        graphData={graphData}
        nodeId="id"
        nodeCanvasObject={paintNode}
        nodePointerAreaPaint={paintArea}
        linkColor={() => "#334155"}
        linkWidth={1}
        linkDirectionalParticles={1}
        linkDirectionalParticleWidth={2}
        linkDirectionalParticleColor={() => "#6366f1"}
        onNodeClick={handleNodeClick}
        backgroundColor="#020617"
        cooldownTicks={100}
        warmupTicks={50}
      />
    </div>
  );
}
