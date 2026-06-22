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
  // Live telemetry the canvas renders on each node (Phase 2).
  liveText?: string; // latest wolf_progress beat — what this wolf is doing right now
  phase?: string; // latest wolf_progress phase (searching | reading | thinking | …)
  sources: number; // hits this wolf has gathered (from tool_result)
  spendUsd: number; // this wolf's cumulative spend (from tokens_spent)
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

export interface PlanStep {
  step_id: string;
  summary: string;
  wolves: string[];
}

export interface PlanView {
  steps: PlanStep[];
  wolves: string[];
  pattern: string;
  assumptions: string[];
  est_cost: number;
  est_time: number;
  strategy?: string; // the selected research strategy (additive plan_proposed field)
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
  plan: PlanView | null;
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
    plan: null,
  };
}

// Narrow a payload field without `any`.
function f<T = string>(ev: PackEvent, key: string): T {
  return ev.payload[key] as T;
}

function patchWolf(
  s: HuntView,
  wolfId: string | undefined,
  patch: Partial<WolfView>,
): Record<string, WolfView> {
  if (!wolfId || !s.wolves[wolfId]) return s.wolves;
  return { ...s.wolves, [wolfId]: { ...s.wolves[wolfId], ...patch } };
}

function setWolf(
  s: HuntView,
  wolfId: string | undefined,
  status: WolfStatus,
): Record<string, WolfView> {
  return patchWolf(s, wolfId, { status });
}

// wolf_progress phases that mean "deliberating" (shimmer) vs "actively working".
const THINKING_PHASES = new Set(["thinking", "critiquing"]);

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
      return {
        ...s,
        state: "plan_ready",
        plan: {
          steps: f<PlanStep[]>(ev, "steps"),
          wolves: f<string[]>(ev, "wolves"),
          pattern: f(ev, "pattern"),
          assumptions: f<string[]>(ev, "assumptions"),
          est_cost: f<number>(ev, "est_cost"),
          est_time: f<number>(ev, "est_time"),
          strategy: ev.payload["strategy"] as string | undefined,
        },
      };

    case "plan_edited": {
      // The user tweaked the plan before launch; reflect edited assumptions in the shown plan.
      const diff = (ev.payload["diff"] ?? {}) as { assumptions?: string[] };
      const plan =
        s.plan && Array.isArray(diff.assumptions) ? { ...s.plan, assumptions: diff.assumptions } : s.plan;
      return { ...s, plan, feed: feed(s, ev, "Updated the plan before the hunt.") };
    }

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
            sources: 0,
            spendUsd: 0,
          },
        },
      };
    }

    case "step_started":
      return { ...s, wolves: setWolf(s, f(ev, "wolf_id"), "hunting") };

    case "step_completed":
      // Work done — keep the last liveText as the node's result line, but stop deliberating.
      return { ...s, wolves: patchWolf(s, f(ev, "wolf_id"), { status: "done", phase: undefined }) };

    case "wolf_progress": {
      const wolfId = f(ev, "wolf_id");
      if (!s.wolves[wolfId]) return s;
      const phase = f(ev, "phase");
      // A live beat only deliberates/works a wolf that hasn't already finished its step.
      const cur = s.wolves[wolfId].status;
      const status: WolfStatus =
        cur === "done" || cur === "stray"
          ? cur
          : THINKING_PHASES.has(phase)
            ? "thinking"
            : "hunting";
      return {
        ...s,
        wolves: patchWolf(s, wolfId, { status, phase, liveText: f(ev, "text") }),
      };
    }

    case "message_passed": {
      const from = f(ev, "from_wolf");
      // Don't resurrect a finished wolf into "talking" — a handoff at completion stays done.
      const status = s.wolves[from]?.status === "done" ? "done" : "talking";
      return {
        ...s,
        wolves: patchWolf(s, from, { status }),
        feed: feed(s, ev, `${from} handed off to ${f(ev, "to_wolf")}: ${f(ev, "summary")}`),
      };
    }

    case "tool_called":
      return { ...s, feed: feed(s, ev, `${f(ev, "wolf_id")} is searching: ${f(ev, "args_summary")}`) };

    case "tool_result": {
      const wolfId = f(ev, "wolf_id");
      const hits = Number(ev.payload["hits"] ?? 0);
      const w = s.wolves[wolfId];
      if (!w || !hits) return s;
      return { ...s, wolves: patchWolf(s, wolfId, { sources: w.sources + hits }) };
    }

    case "tokens_spent": {
      const wolfId = f(ev, "wolf_id");
      const w = s.wolves[wolfId];
      const wolves = w
        ? patchWolf(s, wolfId, { spendUsd: w.spendUsd + Number(f<number>(ev, "cost_usd") || 0) })
        : s.wolves;
      // Spend resuming after a Boundary halt means the human raised the cap — leave the halt.
      const resumed = s.state === "halted_boundary";
      const status: BoundaryStatus = resumed ? "normal" : s.boundary.status;
      return {
        ...s,
        state: resumed ? "hunting" : s.state,
        wolves,
        boundary: boundaryWith(s, f<number>(ev, "cumulative_usd"), status),
      };
    }

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

    case "standoff_turn":
      return { ...s, feed: feed(s, ev, f(ev, "argument_summary")) };

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

    case "input_added":
      return {
        ...s,
        feed: feed(
          s,
          ev,
          f<boolean>(ev, "mid_hunt") ? "You added context to the hunt." : "Added your material to the hunt.",
        ),
      };

    case "transcript_ready":
      return { ...s, feed: feed(s, ev, "Transcribed your audio into the hunt.") };

    case "benchmark_started":
      return { ...s, feed: feed(s, ev, "Benchmarking the pack against a lone wolf…") };

    case "benchmark_completed":
      return { ...s, feed: feed(s, ev, "The scorecard is ready.") };

    default:
      return s;
  }
}

export function reduceAll(events: PackEvent[]): HuntView {
  return events.reduce(reduce, initialHuntView());
}
