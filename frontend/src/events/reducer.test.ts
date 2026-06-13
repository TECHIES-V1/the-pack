// Reducer snapshot test (Doc 03 §8): "given stream X, the final state is Y."
// Reads the committed fixture pack so the frontend and backend test the SAME corpus.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { reduceAll, initialHuntView, reduce } from "./reducer";
import type { PackEvent } from "./types";

const here = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES = path.resolve(here, "../../../fixtures");

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
