// Reducer snapshot test (Doc 03 §8): "given stream X, the final state is Y."
// Reads the committed fixture pack so the frontend and backend test the SAME corpus.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { reduceAll, initialHuntView, reduce } from "./reducer";
import type { PackEvent } from "./types";

const here = path.dirname(fileURLToPath(import.meta.url));
// Frontend carries its own copy of the fixture pack (frontend/fixtures) so the team never
// reaches outside this folder. Canonical copy lives in backend/fixtures; keep them in sync.
const FIXTURES = path.resolve(here, "../../fixtures");

function load(name: string): PackEvent[] {
  return readFileSync(path.join(FIXTURES, name), "utf-8")
    .split("\n")
    .filter((l) => l.trim())
    .map((l) => JSON.parse(l) as PackEvent);
}

describe("reducer over the fixture pack", () => {
  it("Flow A ends returned, with the final artifact and 6 wolves", () => {
    const state = reduceAll(load("flow_a_researcher.jsonl"));
    expect(state.state).toBe("returned");
    expect(state.finalArtifactId).toBe("art_a_final");
    expect(Object.keys(state.wolves)).toHaveLength(8); // alpha+beta+3 scouts+tracker+sentinel+howler
    expect(state.boundary.cumulativeUsd).toBeCloseTo(0.45, 2);
  });

  it("boundary_halt ends halted at 100%", () => {
    const state = reduceAll(load("boundary_halt.jsonl"));
    expect(state.state).toBe("halted_boundary");
    expect(state.boundary.status).toBe("halted");
    expect(state.boundary.pct).toBeGreaterThanOrEqual(100);
  });

  it("standoff_stray recovers the stray and resolves the standoff", () => {
    const events = load("standoff_stray.jsonl");
    const state = reduceAll(events);
    expect(state.activeStandoffId).toBeNull();
    expect(state.state).toBe("returned");
    // scout-1 strayed, then Alpha rerouted to scout-2; scout-1 stops alerting (becomes done).
    expect(state.wolves["scout-1"].status).toBe("done");
  });

  it("living canvas: per-wolf live text, sources, spend, and strategy land on the view", () => {
    const state = reduceAll(load("living_canvas.jsonl"));
    expect(state.state).toBe("returned");
    expect(state.finalArtifactId).toBe("art_lc_final");
    expect(state.plan?.strategy).toBe("orchestrate");

    const scout = state.wolves["scout-1"];
    expect(scout.status).toBe("done"); // handoff after completion doesn't resurrect it to "talking"
    expect(scout.sources).toBe(3); // from tool_result hits
    expect(scout.spendUsd).toBeCloseTo(0.02, 2); // per-wolf spend
    expect(scout.liveText).toBe("Reading 3 sources"); // last wolf_progress beat is retained

    expect(state.wolves["tracker"].status).toBe("done");
    expect(state.boundary.cumulativeUsd).toBeCloseTo(0.3, 2);
  });

  it("is a pure function: replays identically and ignores stale seq", () => {
    const events = load("flow_b_meeting.jsonl");
    const once = reduceAll(events);
    const twice = reduceAll(events);
    expect(twice).toEqual(once);
    // Folding an already-seen seq is a no-op.
    const s = reduceAll(events);
    expect(reduce(s, events[0])).toBe(s);
    void initialHuntView();
  });
});

// The chat narration is the reducer's `feed`: each event the user should hear about becomes one
// Alpha-voice line, in order. These pin the wording so the chat stays substantive, not robotic.
function ev(type: string, payload: Record<string, unknown>, seq: number): PackEvent {
  return {
    event_id: `e${seq}`,
    hunt_id: "h1",
    seq,
    ts: "2026-01-01T00:00:00Z",
    type: type as PackEvent["type"],
    actor: "engine",
    payload,
  };
}

const feedTexts = (events: PackEvent[]): string[] => reduceAll(events).feed.map((f) => f.text);

describe("reducer narration (the chat feed)", () => {
  it("voices the key beats in Alpha's words, in order", () => {
    const texts = feedTexts([
      ev("plan_proposed", { steps: [], wolves: [], pattern: "p", assumptions: [], est_cost: 0, est_time: 0, queries: ["a", "b", "c"] }, 1),
      ev("plan_approved", { boundary_usd: 1 }, 2),
      ev("wolf_spawned", { wolf_id: "tracker", role: "tracker", model_tier: "plus", thinking: true }, 3),
      ev("step_started", { wolf_id: "tracker", step_id: "s2", summary: "merge" }, 4),
      ev("message_passed", { from_wolf: "scout-1", to_wolf: "tracker", intent: "handoff_findings", summary: "5 launches confirmed" }, 5),
      ev("hold_opened", { hold_id: "h1", question: "A or B?", options: ["A", "B"], recommended: "A" }, 6),
      ev("hunt_completed", { final_artifact_id: "art_f", totals: {} }, 7),
    ]);
    expect(texts).toEqual([
      "On it — sending the scouts out on 3 angles.",
      "Tracker's cross-referencing what the scouts found.",
      "scout-1 is back: 5 launches confirmed",
      "I hit a fork — I need your call below: A or B?",
      "Your brief's ready.",
    ]);
  });

  it("voices the failure paths", () => {
    expect(feedTexts([ev("boundary_halt", {}, 1)])).toContain(
      "Paused — the next step would cross your cap. Raise it to keep going.",
    );
    expect(feedTexts([ev("hunt_failed", { reason_plain_english: "engine error" }, 1)])).toContain(
      "This one didn't come together: engine error",
    );
  });

  it("keeps per-search noise out of the chat", () => {
    expect(feedTexts([ev("tool_called", { wolf_id: "scout-1", tool: "web_search", args_summary: "x" }, 1)])).toHaveLength(0);
  });
});
