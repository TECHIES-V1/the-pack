// FormationPreview — a small, static node-map of a TEAM (no live hunt). Reuses the Territory's
// data-driven buildGraph + WolfNode so the Plan's Edit Panel (and, later, Instinct cards) can show
// "where the pack will arrange itself" before a single event fires. Non-interactive.

import { useMemo } from "react";
import { Background, ReactFlow, ReactFlowProvider, type Edge, type Node } from "@xyflow/react";

import { buildGraph } from "./Territory";
import { nodeTypes } from "./WolfNode";
import type { TeamMember, WolfView } from "@/events/reducer";
import type { WolfRole, WolfStatus } from "@/events/types";

// Mirror the engine's id convention so the preview matches what will spawn (supervisor `_wolf_ids`).
function wolfIds(role: string, count: number): string[] {
  const n = Math.max(1, count);
  if (role === "scout") return Array.from({ length: n }, (_, i) => `scout-${i + 1}`);
  if (n <= 1) return [role];
  return Array.from({ length: n }, (_, i) => `${role}-${i + 1}`);
}

function teamToWolves(team: TeamMember[]): WolfView[] {
  const out: WolfView[] = [];
  for (const m of team) {
    for (const id of wolfIds(m.role, m.count)) {
      out.push({
        wolfId: id,
        role: m.role as WolfRole,
        status: "idle" as WolfStatus,
        tier: (m.tier ?? "plus") as "max" | "plus" | "flash",
        thinking: m.thinking ?? false,
        sources: 0,
        spendUsd: 0,
        budgetUsd: m.budget_usd,
      });
    }
  }
  return out;
}

export function FormationPreview({ team, height = 200 }: { team: TeamMember[]; height?: number }) {
  const { nodes, edges } = useMemo<{ nodes: Node[]; edges: Edge[] }>(
    () => buildGraph(teamToWolves(team)),
    [team],
  );
  return (
    <ReactFlowProvider>
      <div style={{ width: "100%", height, borderRadius: 10, overflow: "hidden" }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          proOptions={{ hideAttribution: true }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          zoomOnScroll={false}
          zoomOnPinch={false}
          panOnDrag={false}
          preventScrolling={false}
        >
          <Background color="#242424" gap={18} size={1} />
        </ReactFlow>
      </div>
    </ReactFlowProvider>
  );
}
