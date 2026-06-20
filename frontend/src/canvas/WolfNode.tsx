// WolfNode — a wolf as a living node on the Territory (Doc 03 §6, Phase 2).
//
// Color is by ROLE; the STATE changes the treatment:
//   idle (dim ring) · hunting (solid + glow) · talking (solid + line) · holding (white ring,
//   paused) · stray (solid red, any role) · done (solid green, any role) · thinking (shimmer).
//
// Beyond the circle, an active wolf now shows what it's actually doing: its tier, its live
// action line (the latest wolf_progress beat), and its running source count + spend. Half the
// design — a node you can read at a glance — was built and never wired; this wires it.

import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { CSSProperties, ReactNode } from "react";
import { FaStar, FaExclamationTriangle } from "react-icons/fa";
import { LuRoute, LuPen } from "react-icons/lu";
import { BiSolidBarChartAlt2 } from "react-icons/bi";
import { PiCrosshairBold, PiHexagonBold } from "react-icons/pi";

import type { WolfRole, WolfStatus } from "@/events/types";

// Hex (not CSS vars) so we can build glow colors with alpha suffixes.
export const ROLE_COLOR: Record<WolfRole, string> = {
  alpha: "#e6a23c",
  beta: "#3fb27f",
  scout: "#5b9bd5",
  tracker: "#eb3424",
  howler: "#c084fc",
  sentinel: "#9ca3af",
  hunter: "#22d3ee",
  elder: "#9ca3af",
};

const ROLE_ICON: Record<WolfRole, ReactNode> = {
  alpha: <FaStar />,
  beta: <BiSolidBarChartAlt2 />,
  scout: <LuRoute />,
  tracker: <PiCrosshairBold />,
  howler: <LuPen />,
  sentinel: <FaExclamationTriangle />,
  hunter: <PiHexagonBold />,
  elder: <FaStar />,
};

const STRAY = "#eb3424";
const DONE = "#3fb27f";
const IDLE_RING = "#3a3a3a";
const IDLE_ICON = "#6b7280";
const PANEL = "#1a1a1a";

const ACTIVE = new Set<WolfStatus>(["hunting", "talking", "thinking", "holding"]);

interface NodeStyle {
  fill: string;
  ring: string;
  icon: string;
  glow: string | null;
  shimmer: boolean;
}

function nodeStyle(role: WolfRole, status: WolfStatus): NodeStyle {
  const c = ROLE_COLOR[role];
  switch (status) {
    case "hunting":
    case "talking":
      return { fill: c, ring: c, icon: "#fff", glow: c, shimmer: false };
    case "thinking":
      return { fill: "transparent", ring: c, icon: c, glow: c, shimmer: true };
    case "holding":
      return { fill: PANEL, ring: "#ffffff", icon: "#ffffff", glow: null, shimmer: false };
    case "stray":
      return { fill: STRAY, ring: STRAY, icon: "#fff", glow: STRAY, shimmer: false };
    case "done":
      return { fill: DONE, ring: DONE, icon: "#fff", glow: null, shimmer: false };
    case "idle":
    default:
      return { fill: "transparent", ring: IDLE_RING, icon: IDLE_ICON, glow: null, shimmer: false };
  }
}

export interface WolfNodeData {
  wolfId: string;
  role: WolfRole;
  status: WolfStatus;
  tier: "max" | "plus" | "flash";
  thinking: boolean;
  liveText?: string;
  phase?: string;
  sources?: number;
  spendUsd?: number;
  [key: string]: unknown;
}

function truncate(text: string, n: number): string {
  return text.length > n ? text.slice(0, n - 1).trimEnd() + "…" : text;
}

export function WolfCard({ data, selected = false }: { data: WolfNodeData; selected?: boolean }) {
  const s = nodeStyle(data.role, data.status);
  const active = ACTIVE.has(data.status);
  const sources = data.sources ?? 0;
  const spend = data.spendUsd ?? 0;

  const circle: CSSProperties = {
    width: 52,
    height: 52,
    borderRadius: 9999,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 20,
    background: s.fill,
    border: `2px solid ${s.ring}`,
    color: s.icon,
    boxShadow: s.glow ? `0 0 18px ${s.glow}66, 0 0 0 4px ${s.glow}22` : "none",
    outline: selected ? "2px solid rgba(255,255,255,0.25)" : "none",
    outlineOffset: 3,
    transition:
      "background var(--motion-base) var(--easing), border-color var(--motion-base) var(--easing), box-shadow var(--motion-base) var(--easing)",
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 5,
        width: 156,
        fontFamily: "var(--font-sans)",
      }}
    >
      <div className={s.shimmer ? "animate-shimmer" : ""} style={circle}>
        {ROLE_ICON[data.role]}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 5, lineHeight: 1 }}>
        <span style={{ fontSize: 12, color: "#e4e4e7", textTransform: "capitalize" }}>
          {data.role}
        </span>
        <span
          style={{
            fontSize: 9,
            letterSpacing: 0.3,
            textTransform: "uppercase",
            color: "#9ca3af",
            background: "#0f0f0f",
            border: "1px solid #2a2a2a",
            borderRadius: 4,
            padding: "1px 4px",
          }}
        >
          {data.tier}
        </span>
      </div>

      {active && data.liveText ? (
        <div
          style={{
            fontSize: 10.5,
            lineHeight: 1.3,
            color: "#a1a1aa",
            textAlign: "center",
            maxWidth: 156,
            minHeight: 26,
          }}
        >
          {truncate(data.liveText, 56)}
        </div>
      ) : null}

      {sources > 0 || spend > 0 ? (
        <div style={{ display: "flex", gap: 8, fontSize: 9.5, color: "#71717a" }}>
          {sources > 0 && <span>{sources} src</span>}
          {spend > 0 && <span>${spend.toFixed(2)}</span>}
        </div>
      ) : null}
    </div>
  );
}

export function WolfNode({ data, selected }: NodeProps) {
  return (
    <>
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <WolfCard data={data as WolfNodeData} selected={selected} />
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </>
  );
}

export const nodeTypes = { wolf: WolfNode };
