// WolfNode — a wolf rendered as itself, not a box (Doc 03 §3, §6).
//
// State-driven styling pattern adapted from Firecrawl's Open Agent Builder CustomNode
// (MIT) — see docs/BORROWING.md. The states are the Doc 03 §6 matrix:
//   idle · hunting · talking · holding · stray · done · thinking (shimmer)
//
// Every state is visibly distinct. No state changes without an event.
//
// Split in two: WolfCard is presentational (used by the states gallery and the canvas);
// WolfNode wraps it with React Flow Handles for live connections.

import { Handle, Position, type NodeProps } from "@xyflow/react";

import type { WolfRole, WolfStatus } from "@/events/types";

export interface WolfNodeData {
  wolfId: string;
  role: WolfRole;
  status: WolfStatus;
  tier: "max" | "plus" | "flash";
  thinking: boolean;
  [key: string]: unknown;
}

const STATUS_COLOR: Record<WolfStatus, string> = {
  idle: "var(--wolf-idle)",
  hunting: "var(--wolf-hunting)",
  talking: "var(--wolf-talking)",
  holding: "var(--wolf-holding)",
  stray: "var(--wolf-stray)",
  done: "var(--wolf-done)",
  thinking: "var(--wolf-hunting)",
};

const STATUS_LABEL: Record<WolfStatus, string> = {
  idle: "waiting",
  hunting: "on the hunt",
  talking: "handing off",
  holding: "holding",
  stray: "strayed",
  done: "done",
  thinking: "thinking",
};

export function WolfCard({ data, selected = false }: { data: WolfNodeData; selected?: boolean }) {
  const color = STATUS_COLOR[data.status];
  // Alpha and Sentinel carry the thinking shimmer (Doc 02 §4 / Doc 03 §6).
  const shimmer = data.status === "thinking" || (data.thinking && data.status === "hunting");

  return (
    <div
      data-status={data.status}
      className={shimmer ? "animate-shimmer" : ""}
      style={{
        minWidth: 150,
        padding: "10px 14px",
        borderRadius: 12,
        background: "#fff",
        border: `2px solid ${color}`,
        outline: selected ? "2px solid rgba(31,42,60,0.18)" : "2px solid transparent",
        boxShadow: data.status === "hunting" ? `0 0 0 4px ${color}22` : "none",
        transition: "border-color var(--motion-base) var(--easing)",
        fontFamily: "var(--font-sans)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span aria-hidden style={{ width: 8, height: 8, borderRadius: 9999, background: color }} />
        <strong style={{ textTransform: "capitalize", color: "var(--ink)" }}>{data.role}</strong>
        <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--wolf-idle)" }}>{data.tier}</span>
      </div>
      <div style={{ fontSize: 12, color, marginTop: 4 }}>{STATUS_LABEL[data.status]}</div>
    </div>
  );
}

export function WolfNode({ data, selected }: NodeProps) {
  return (
    <>
      <Handle type="target" position={Position.Left} />
      <WolfCard data={data as WolfNodeData} selected={selected} />
      <Handle type="source" position={Position.Right} />
    </>
  );
}

export const nodeTypes = { wolf: WolfNode };
