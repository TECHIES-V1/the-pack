// Event types — the frontend mirror of schema/events.schema.json (the frozen contract).
// Keep in lockstep with the JSON Schema and the Pydantic models. A schema change is one PR
// that touches all three.

export type EventType =
  | "hunt_created"
  | "input_added"
  | "transcript_ready"
  | "plan_proposed"
  | "plan_edited"
  | "plan_approved"
  | "wolf_spawned"
  | "step_started"
  | "step_completed"
  | "message_passed"
  | "tool_called"
  | "tool_result"
  | "tokens_spent"
  | "hold_opened"
  | "hold_resolved"
  | "standoff_opened"
  | "standoff_turn"
  | "standoff_resolved"
  | "stray_detected"
  | "stray_recovered"
  | "boundary_warning"
  | "boundary_downgrade"
  | "boundary_halt"
  | "artifact_created"
  | "hunt_completed"
  | "hunt_failed"
  | "hunt_stopped"
  | "benchmark_started"
  | "benchmark_completed";

export interface PackEvent {
  event_id: string;
  hunt_id: string;
  seq: number;
  ts: string;
  type: EventType;
  actor: string;
  // Payload is the per-type object from schema §3.2. Typed loosely at the seam; the
  // reducer narrows by `type`.
  payload: Record<string, unknown>;
}

export type WolfRole =
  | "alpha"
  | "beta"
  | "scout"
  | "tracker"
  | "howler"
  | "sentinel"
  | "hunter"
  | "elder";

// The Doc 03 §6 WolfNode state matrix.
export type WolfStatus =
  | "idle"
  | "hunting"
  | "talking"
  | "holding"
  | "stray"
  | "done"
  | "thinking";

// The hunt state machine (Doc 02 §3).
export type HuntState =
  | "draft"
  | "planning"
  | "plan_ready"
  | "hunting"
  | "holding"
  | "standoff"
  | "finishing"
  | "returned"
  | "halted_boundary"
  | "stopped_by_user"
  | "failed";

export type BoundaryStatus = "normal" | "warn" | "downgraded" | "halted";
