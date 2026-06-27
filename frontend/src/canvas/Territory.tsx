// The Territory — the pack working live on a dark canvas (Doc 02 §S3, Doc 03 §3).
// Draws ENTIRELY from the hunt store (pure reducer over the event stream). Nodes are wolves
// (WolfNode); edges follow the plan's spine and animate per the design board:
//   dormant (grey dotted) · flowing (role-colored, animated) · blocked (red, on a stray).

import { useMemo, type CSSProperties } from "react";
import {
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
} from "@xyflow/react";

import { ROLE_COLOR, nodeTypes, type WolfNodeData } from "./WolfNode";
import { layoutPack } from "./packLayout";
import type { HuntView, WolfView } from "@/events/reducer";
import type { HuntState } from "@/events/types";
import type { WolfRole, WolfStatus } from "@/events/types";

const HUNT_STATE_LABEL: Record<HuntState, string> = {
  draft: "Starting up",
  planning: "Planning the hunt",
  plan_ready: "Plan ready — awaiting your approval",
  hunting: "Hunt in progress",
  finishing: "Pack finishing up",
  holding: "Pack paused — your input needed",
  standoff: "Pack debating a claim",
  halted_boundary: "Hunt paused — budget limit reached",
  returned: "Hunt complete",
  failed: "Hunt failed",
  stopped_by_user: "Hunt stopped",
};

type EdgeState = "dormant" | "flowing" | "blocked";

const ACTIVE = new Set(["hunting", "talking", "thinking"]);

const ROLES: WolfRole[] = ["alpha", "beta", "scout", "tracker", "howler", "sentinel", "hunter", "elder"];
const TIER_BY_ROLE: Record<WolfRole, "max" | "plus" | "flash"> = {
  alpha: "max", beta: "plus", scout: "flash", tracker: "plus",
  howler: "plus", sentinel: "max", hunter: "flash", elder: "plus",
};

function roleFromId(id: string): WolfRole {
  const base = id.split("-")[0] as WolfRole;
  return ROLES.includes(base) ? base : "scout";
}

// Real spawned wolves once the hunt starts; otherwise the PLANNED pack shown idle so the canvas
// isn't blank during plan review (the wolves come from plan_proposed; alpha/beta lead the pack).
function displayWolves(view: HuntView): WolfView[] {
  const real = Object.values(view.wolves);
  if (real.length) return real;
  if (!view.plan) return [];
  const ids = ["alpha", "beta", ...view.plan.wolves];
  const seen = new Set<string>();
  return ids
    .filter((id) => (seen.has(id) ? false : (seen.add(id), true)))
    .map((id) => {
      const role = roleFromId(id);
      return {
        wolfId: id,
        role,
        status: "idle" as WolfStatus,
        tier: TIER_BY_ROLE[role],
        thinking: false,
        sources: 0,
        spendUsd: 0,
      };
    });
}

function edgeState(from: WolfView | undefined, to: WolfView | undefined): EdgeState {
  if (!from || !to) return "dormant";
  if (from.status === "stray" || to.status === "stray") return "blocked";
  if (ACTIVE.has(from.status) || from.status === "done") return "flowing";
  return "dormant";
}

function styleFor(state: EdgeState, color: string): CSSProperties {
  if (state === "blocked") return { stroke: "var(--territory-edge-blocked)", strokeWidth: 2 };
  if (state === "flowing") return { stroke: color, strokeWidth: 2 };
  return { stroke: "var(--territory-edge)", strokeWidth: 1.5, strokeDasharray: "3 5" };
}

function buildGraph(view: HuntView): { nodes: Node[]; edges: Edge[] } {
  const wolves = displayWolves(view);
  const byRole = (role: string) => wolves.filter((w) => w.role === role);
  const first = (role: string) => byRole(role)[0];

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
      liveText: w.liveText,
      phase: w.phase,
      sources: w.sources,
      spendUsd: w.spendUsd,
    } satisfies WolfNodeData,
  }));

  // The plan's spine: Alpha → Beta → Scouts (parallel) → Tracker → Howler → Hunter;
  // Sentinel watches from Alpha. Only link wolves that exist on the canvas.
  const alpha = first("alpha");
  const beta = first("beta");
  const tracker = first("tracker");
  const howler = first("howler");
  const hunter = first("hunter");
  const sentinel = first("sentinel");
  const scouts = byRole("scout");

  const links: Array<[WolfView | undefined, WolfView | undefined]> = [];
  if (alpha && beta) links.push([alpha, beta]);
  scouts.forEach((s) => {
    links.push([beta ?? alpha, s]);
    if (tracker) links.push([s, tracker]);
  });
  if (!scouts.length && tracker) links.push([beta ?? alpha, tracker]);
  if (tracker && howler) links.push([tracker, howler]);
  if (howler && hunter) links.push([howler, hunter]);
  if (alpha && sentinel) links.push([alpha, sentinel]);

  const edges: Edge[] = links
    .filter(([a, b]) => a && b && a.wolfId !== b.wolfId)
    .map(([a, b]) => {
      const state = edgeState(a, b);
      return {
        id: `${a!.wolfId}->${b!.wolfId}`,
        source: a!.wolfId,
        target: b!.wolfId,
        type: "smoothstep",
        animated: state === "flowing",
        style: styleFor(state, ROLE_COLOR[a!.role]),
      } satisfies Edge;
    });

  return { nodes: layoutPack(nodes, edges), edges };
}

export function Territory({ view }: { view: HuntView }) {
  const { nodes, edges } = useMemo(() => buildGraph(view), [view]);

  return (
    <ReactFlowProvider>
      <div style={{ position: "relative", width: "100%", height: "100%", background: "var(--territory-bg)" }}>
        {/* Screen-reader-only live region announcing overall hunt state */}
        <div
          aria-live="polite"
          aria-atomic="true"
          className="sr-only"
        >
          {HUNT_STATE_LABEL[view.state] ?? view.state}
        </div>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#242424" gap={22} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </ReactFlowProvider>
  );
}
