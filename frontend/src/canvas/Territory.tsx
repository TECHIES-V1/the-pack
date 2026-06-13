// The Territory — wolves working live (Doc 02 §S3, Doc 03 §3). Draws ENTIRELY from the
// hunt store, which is produced by the pure reducer over the event stream. No canvas-only
// logic, no second brain.

import { useMemo } from "react";
import {
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
} from "@xyflow/react";

import { nodeTypes, type WolfNodeData } from "./WolfNode";
import { layoutPack } from "./packLayout";
import type { HuntView } from "@/events/reducer";

function buildGraph(view: HuntView): { nodes: Node[]; edges: Edge[] } {
  const wolves = Object.values(view.wolves);
  const nodes: Node[] = wolves.map((w) => ({
    id: w.wolfId,
    type: "wolf",
    position: { x: 0, y: 0 }, // dagre fills this in
    data: {
      wolfId: w.wolfId,
      role: w.role,
      status: w.status,
      tier: w.tier,
      thinking: w.thinking,
    } satisfies WolfNodeData,
  }));

  // Alpha anchors; everyone else hangs off Alpha (a plan-shaped graph comes later).
  const alpha = wolves.find((w) => w.role === "alpha");
  const edges: Edge[] = alpha
    ? wolves
        .filter((w) => w.wolfId !== alpha.wolfId)
        .map((w) => {
          const active = w.status === "hunting" || w.status === "talking";
          return {
            id: `${alpha.wolfId}->${w.wolfId}`,
            source: alpha.wolfId,
            target: w.wolfId,
            type: "smoothstep",
            animated: active, // EdgeFlow: flowing vs dormant
            style: { stroke: active ? "var(--wolf-hunting)" : "var(--wolf-idle)", strokeWidth: active ? 2 : 1 },
          } satisfies Edge;
        })
    : [];

  return { nodes: layoutPack(nodes, edges), edges };
}

export function Territory({ view }: { view: HuntView }) {
  const { nodes, edges } = useMemo(() => buildGraph(view), [view]);

  return (
    <ReactFlowProvider>
      <div style={{ width: "100%", height: "100%" }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#E5E0D6" gap={20} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </ReactFlowProvider>
  );
}
