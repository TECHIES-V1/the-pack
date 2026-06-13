// PackLayout — React Flow does not auto-place nodes, so dagre arranges the pack
// (Doc 03 §3). Alpha anchors; wolves arrange by the plan. Pure: nodes/edges in, positioned
// nodes out.

import dagre from "dagre";
import { Position, type Edge, type Node } from "@xyflow/react";

const NODE_W = 160;
const NODE_H = 64;

export function layoutPack(nodes: Node[], edges: Edge[], direction: "LR" | "TB" = "LR"): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, nodesep: 40, ranksep: 80 });

  nodes.forEach((n) => g.setNode(n.id, { width: NODE_W, height: NODE_H }));
  edges.forEach((e) => g.setEdge(e.source, e.target));

  dagre.layout(g);

  return nodes.map((n) => {
    const { x, y } = g.node(n.id);
    return {
      ...n,
      position: { x: x - NODE_W / 2, y: y - NODE_H / 2 },
      sourcePosition: direction === "LR" ? Position.Right : Position.Bottom,
      targetPosition: direction === "LR" ? Position.Left : Position.Top,
    };
  });
}
