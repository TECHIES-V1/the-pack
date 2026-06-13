// The pure reducer — the golden rule made code (Doc 03 §2, §4).
//
//   "The client is a deterministic function: the event log in, the UI state out."
//
// No side effects. No business logic. No derived truths the backend never emitted. Feed
// this the event log and get the UI state. The same function powers the Territory, the
// Activity Feed, the Boundary meter, and Tracks. Unit-tested against the fixture pack.

import type {
  BoundaryStatus,
  HuntState,
  PackEvent,
  WolfRole,
  WolfStatus,
} from "./types";

export interface WolfView {
  wolfId: string;
  role: WolfRole;
  status: WolfStatus;
  tier: "max" | "plus" | "flash";
  thinking: boolean;
}

export interface FeedLine {
  seq: number;
  ts: string;
  text: string; // product voice — a sentence, never a raw event
}

export interface HoldView {
  holdId: string;
  question: string;
  options: string[];
  recommended: string;
}

export interface BoundaryView {
  boundaryUsd: number;
  cumulativeUsd: number;
  pct: number;
  status: BoundaryStatus;
}

export interface HuntView {
  huntId: string | null;
  state: HuntState;
  lastSeq: number;
  wolves: Record<string, WolfView>;
  feed: FeedLine[];
  boundary: BoundaryView;
  openHold: HoldView | null;
  activeStandoffId: string | null;
  finalArtifactId: string | null;
  totals: Record<string, unknown> | null;
}

export function initialHuntView(): HuntView {
  return {
    huntId: null,
    state: "draft",
    lastSeq: -1,
    wolves: {},
    feed: [],
    boundary: { boundaryUsd: 0, cumulativeUsd: 0, pct: 0, status: "normal" },
    openHold: null,
    activeStandoffId: null,
    finalArtifactId: null,
    totals: null,
  };
}

// Narrow a payload field without `any`.
function f<T = string>(ev: PackEvent, key: string): T {
  return ev.payload[key] as T;
}

function setWolf(
  s: HuntView,
  wolfId: string | undefined,
  status: WolfStatus,
): Record<string, WolfView> {
  if (!wolfId || !s.wolves[wolfId]) return s.wolves;
  return { ...s.wolves, [wolfId]: { ...s.wolves[wolfId], status } };
}

function feed(s: HuntView, ev: PackEvent, text: string): FeedLine[] {
  return [...s.feed, { seq: ev.seq, ts: ev.ts, text }];
}

function boundaryWith(
  s: HuntView,
  cumulativeUsd: number,
  status?: BoundaryStatus,
): BoundaryView {
  const b = s.boundary;
  const pct = b.boundaryUsd > 0 ? (cumulativeUsd / b.boundaryUsd) * 100 : 0;
  return { ...b, cumulativeUsd, pct, status: status ?? b.status };
}

export function reduce(state: HuntView, ev: PackEvent): HuntView {
  // seq is strictly increasing per hunt; ignore anything we've already folded in.
  if (ev.seq <= state.lastSeq) return state;
  const s = { ...state, huntId: state.huntId ?? ev.hunt_id, lastSeq: ev.seq };

  switch (ev.type) {
    case "hunt_created":
      return { ...s, state: "planning" };

    case "plan_proposed":
      return { ...s, state: "plan_ready" };

    case "plan_approved":
      return {
        ...s,
        state: "hunting",
        boundary: {
          boundaryUsd: f<number>(ev, "boundary_usd"),
          cumulativeUsd: 0,
          pct: 0,
          status: "normal",
        },
      };

    case "wolf_spawned": {
      const wolfId = f(ev, "wolf_id");
      return {
        ...s,
        wolves: {
          ...s.wolves,
          [wolfId]: {
            wolfId,
            role: f<WolfRole>(ev, "role"),
            status: "idle",
            tier: f<"max" | "plus" | "flash">(ev, "model_tier"),
            thinking: f<boolean>(ev, "thinking"),
          },
        },
      };
    }

    case "step_started":
      return { ...s, wolves: setWolf(s, f(ev, "wolf_id"), "hunting") };

    case "step_completed":
      return { ...s, wolves: setWolf(s, f(ev, "wolf_id"), "done") };

    case "message_passed":
      return {
        ...s,
        wolves: setWolf(s, f(ev, "from_wolf"), "talking"),
        feed: feed(s, ev, `${f(ev, "from_wolf")} handed off to ${f(ev, "to_wolf")}: ${f(ev, "summary")}`),
      };

    case "tool_called":
      return { ...s, feed: feed(s, ev, `${f(ev, "wolf_id")} is searching: ${f(ev, "args_summary")}`) };

    case "tokens_spent":
      return { ...s, boundary: boundaryWith(s, f<number>(ev, "cumulative_usd")) };

    case "hold_opened":
      return {
        ...s,
        state: "holding",
        openHold: {
          holdId: f(ev, "hold_id"),
          question: f(ev, "question"),
          options: f<string[]>(ev, "options"),
          recommended: f(ev, "recommended"),
        },
        feed: feed(s, ev, `The pack is holding: ${f(ev, "question")}`),
      };

    case "hold_resolved":
      return { ...s, state: "hunting", openHold: null };

    case "standoff_opened":
      return {
        ...s,
        state: "standoff",
        activeStandoffId: f(ev, "standoff_id"),
        feed: feed(s, ev, `${f(ev, "challenger")} challenged ${f(ev, "defendant")}.`),
      };

    case "standoff_resolved":
      return {
        ...s,
        state: "hunting",
        activeStandoffId: null,
        feed: feed(s, ev, f(ev, "rationale")),
      };

    case "stray_detected":
      return { ...s, wolves: setWolf(s, f(ev, "wolf_id"), "stray") };

    case "stray_recovered":
      // The strayed wolf's task is abandoned (reroute/replan/respawn); it stops alerting.
      return {
        ...s,
        wolves: setWolf(s, f(ev, "wolf_id"), "done"),
        feed: feed(s, ev, f(ev, "note_plain_english")),
      };

    case "boundary_warning":
      return { ...s, boundary: { ...s.boundary, status: "warn" } };

    case "boundary_downgrade":
      return {
        ...s,
        boundary: { ...s.boundary, status: "downgraded" },
        feed: feed(s, ev, `Eased ${f(ev, "wolf_id")} to a lighter tier to stay inside the Boundary.`),
      };

    case "boundary_halt":
      return {
        ...s,
        state: "halted_boundary",
        boundary: { ...s.boundary, status: "halted" },
        feed: feed(s, ev, `The Boundary stopped the hunt before the next spend.`),
      };

    case "artifact_created":
      return f(ev, "kind") === "final" ? { ...s, finalArtifactId: f(ev, "artifact_id") } : s;

    case "hunt_completed":
      return {
        ...s,
        state: "returned",
        finalArtifactId: f(ev, "final_artifact_id"),
        totals: f<Record<string, unknown>>(ev, "totals"),
      };

    case "hunt_failed":
      return { ...s, state: "failed", feed: feed(s, ev, f(ev, "reason_plain_english")) };

    case "hunt_stopped":
      return { ...s, state: "stopped_by_user" };

    default:
      return s;
  }
}

export function reduceAll(events: PackEvent[]): HuntView {
  return events.reduce(reduce, initialHuntView());
}
