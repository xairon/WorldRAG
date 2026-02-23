"use client";

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import type { SubgraphData, GraphNode } from "@/lib/api";
import { labelColor } from "@/lib/utils";

// Dynamic import to avoid SSR issues with canvas
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
}) as React.ComponentType<Record<string, any>>;

interface ForceGraphProps {
  data: SubgraphData;
  onNodeClick?: (node: GraphNode) => void;
  width?: number;
  height?: number;
}

export default function ForceGraph({
  data,
  onNodeClick,
  width = 800,
  height = 600,
}: ForceGraphProps) {
  const [graphData, setGraphData] = useState<{
    nodes: Record<string, unknown>[];
    links: Record<string, unknown>[];
  }>({ nodes: [], links: [] });

  useEffect(() => {
    if (!data.nodes.length) {
      setGraphData({ nodes: [], links: [] });
      return;
    }

    const nodeIds = new Set(data.nodes.map((n) => n.id));
    const links = data.edges
      .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
      .map((e) => ({ ...e }));

    setGraphData({
      nodes: data.nodes.map((n) => ({ ...n })),
      links,
    });
  }, [data]);

  const handleNodeClick = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (node: any) => {
      if (onNodeClick) {
        onNodeClick(node as GraphNode);
      }
    },
    [onNodeClick]
  );

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
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
  }, []);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const paintArea = useCallback((node: any, color: string, ctx: CanvasRenderingContext2D) => {
    ctx.beginPath();
    ctx.arc(node.x ?? 0, node.y ?? 0, 8, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();
  }, []);

  if (!data.nodes.length) {
    return (
      <div
        className="flex items-center justify-center border border-slate-800 rounded-xl bg-slate-900/30"
        style={{ width, height }}
      >
        <p className="text-slate-500 text-sm">No graph data to display</p>
      </div>
    );
  }

  return (
    <div className="graph-canvas rounded-xl overflow-hidden border border-slate-800 bg-slate-950">
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
