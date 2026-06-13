// A tiny in-repo sample stream so the Territory renders without a backend. The real fuel
// is the fixture pack (../../fixtures) replayed over WS; this is just enough to light up
// the canvas in dev and in the demo-recording mode.

import type { PackEvent } from "@/events/types";

export const sampleStream: PackEvent[] = [
  { event_id: "e0", hunt_id: "demo", seq: 0, ts: "", type: "hunt_created", actor: "user", payload: { source: "typed", raw_input_ref: "r" } },
  { event_id: "e1", hunt_id: "demo", seq: 1, ts: "", type: "plan_proposed", actor: "beta", payload: { steps: [], wolves: [], pattern: "parallel_then_merge", est_cost: 0.6, est_time: 200 } },
  { event_id: "e2", hunt_id: "demo", seq: 2, ts: "", type: "plan_approved", actor: "user", payload: { mode: "on_signal", boundary_usd: 1.0 } },
  { event_id: "e3", hunt_id: "demo", seq: 3, ts: "", type: "wolf_spawned", actor: "engine", payload: { wolf_id: "alpha", role: "alpha", model_tier: "max", thinking: true, prompt_version: "alpha/v1" } },
  { event_id: "e4", hunt_id: "demo", seq: 4, ts: "", type: "wolf_spawned", actor: "engine", payload: { wolf_id: "scout-1", role: "scout", model_tier: "flash", thinking: false, prompt_version: "scout/v1" } },
  { event_id: "e5", hunt_id: "demo", seq: 5, ts: "", type: "wolf_spawned", actor: "engine", payload: { wolf_id: "scout-2", role: "scout", model_tier: "flash", thinking: false, prompt_version: "scout/v1" } },
  { event_id: "e6", hunt_id: "demo", seq: 6, ts: "", type: "wolf_spawned", actor: "engine", payload: { wolf_id: "tracker", role: "tracker", model_tier: "plus", thinking: true, prompt_version: "tracker/v1" } },
  { event_id: "e7", hunt_id: "demo", seq: 7, ts: "", type: "wolf_spawned", actor: "engine", payload: { wolf_id: "sentinel", role: "sentinel", model_tier: "max", thinking: true, prompt_version: "sentinel/v1" } },
  { event_id: "e8", hunt_id: "demo", seq: 8, ts: "", type: "wolf_spawned", actor: "engine", payload: { wolf_id: "howler", role: "howler", model_tier: "plus", thinking: false, prompt_version: "howler/v1" } },
  { event_id: "e9", hunt_id: "demo", seq: 9, ts: "", type: "step_started", actor: "scout-1", payload: { step_id: "s1", wolf_id: "scout-1", summary: "Searching" } },
  { event_id: "e10", hunt_id: "demo", seq: 10, ts: "", type: "step_started", actor: "scout-2", payload: { step_id: "s1", wolf_id: "scout-2", summary: "Searching" } },
  { event_id: "e11", hunt_id: "demo", seq: 11, ts: "", type: "tokens_spent", actor: "scout-1", payload: { wolf_id: "scout-1", model: "qwen-flash", in_tokens: 1000, out_tokens: 400, cost_usd: 0.06, cumulative_usd: 0.72 } },
];
