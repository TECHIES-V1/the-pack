import { z } from 'zod'

const base = z.object({
  event_id: z.string(),
  hunt_id: z.string(),
  seq: z.number().int().nonnegative(),
  ts: z.string(),
  actor: z.string(),
})

// Hunt lifecycle
const HuntCreated = base.extend({
  type: z.literal('hunt_created'),
  payload: z.object({
    source: z.enum(['typed', 'spoken', 'dropped']),
    raw_input_ref: z.string(),
  }),
})

const InputAdded = base.extend({
  type: z.literal('input_added'),
  payload: z.object({
    artifact_id: z.string(),
    kind: z.enum(['audio', 'video', 'pdf', 'csv', 'url', 'text']),
    mid_hunt: z.boolean(),
  }),
})

const TranscriptReady = base.extend({
  type: z.literal('transcript_ready'),
  payload: z.object({
    artifact_id: z.string(),
    provider: z.enum(['qwen_voice', 'qwen_asr']),
    language_hint: z.string().nullable().optional(),
    duration_s: z.number(),
  }),
})

// Plan
const PlanProposed = base.extend({
  type: z.literal('plan_proposed'),
  payload: z.object({
    steps: z.array(z.unknown()),
    wolves: z.array(z.string()),
    pattern: z.enum(['sequential', 'hierarchical', 'parallel_then_merge', 'standoff']),
    assumptions: z.array(z.string()).default([]),
    est_cost: z.number(),
    est_time: z.number(),
    queries: z.array(z.string()).optional(),
    strategy: z.string().optional(),
    team: z.array(z.unknown()).optional(),
    edges: z.array(z.unknown()).optional(),
  }),
})

const PlanEdited = base.extend({
  type: z.literal('plan_edited'),
  payload: z.object({ diff: z.record(z.unknown()) }),
})

const PlanApproved = base.extend({
  type: z.literal('plan_approved'),
  payload: z.object({
    mode: z.enum(['wild', 'on_signal', 'on_command']),
    boundary_usd: z.number(),
  }),
})

// Wolf lifecycle
const WolfSpawned = base.extend({
  type: z.literal('wolf_spawned'),
  payload: z.object({
    wolf_id: z.string(),
    role: z.enum(['alpha', 'beta', 'scout', 'tracker', 'howler', 'sentinel', 'hunter', 'elder', 'doctor']),
    model_tier: z.enum(['max', 'plus', 'flash']),
    thinking: z.boolean(),
    prompt_version: z.string(),
    budget_usd: z.number().nullable().optional(),
    parent_wolf_id: z.string().nullable().optional(),
  }),
})

const StepStarted = base.extend({
  type: z.literal('step_started'),
  payload: z.object({
    step_id: z.string(),
    wolf_id: z.string(),
    summary: z.string(),
  }),
})

const StepCompleted = base.extend({
  type: z.literal('step_completed'),
  payload: z.object({
    step_id: z.string(),
    wolf_id: z.string(),
    output_ref: z.string(),
    confidence: z.number().min(0).max(1),
  }),
})

const MessagePassed = base.extend({
  type: z.literal('message_passed'),
  payload: z.object({
    from_wolf: z.string(),
    to_wolf: z.string(),
    intent: z.string(),
    summary: z.string(),
    ref: z.string().nullable().optional(),
  }),
})

const WolfProgress = base.extend({
  type: z.literal('wolf_progress'),
  payload: z.object({
    wolf_id: z.string(),
    phase: z.enum(['thinking', 'searching', 'reading', 'merging', 'writing', 'critiquing', 'forge']),
    text: z.string(),
    tokens: z.number().nullable().optional(),
  }),
})

// Tools
const ToolCalled = base.extend({
  type: z.literal('tool_called'),
  payload: z.object({
    wolf_id: z.string(),
    tool: z.enum(['web_search', 'web_fetch', 'file_parse', 'transcribe', 'artifact_write']),
    args_summary: z.string(),
  }),
})

const ToolResult = base.extend({
  type: z.literal('tool_result'),
  payload: z.object({
    wolf_id: z.string(),
    tool: z.string(),
    ok: z.boolean(),
    result_ref: z.string().nullable().optional(),
    latency_ms: z.number().int(),
  }),
})

const TokensSpent = base.extend({
  type: z.literal('tokens_spent'),
  payload: z.object({
    wolf_id: z.string(),
    model: z.string(),
    in_tokens: z.number().int(),
    out_tokens: z.number().int(),
    cost_usd: z.number(),
    cumulative_usd: z.number(),
  }),
})

// Holds
const HoldOpened = base.extend({
  type: z.literal('hold_opened'),
  payload: z.object({
    hold_id: z.string(),
    question: z.string(),
    context_ref: z.string().nullable().optional(),
    options: z.array(z.string()),
    recommended: z.string(),
  }),
})

const HoldResolved = base.extend({
  type: z.literal('hold_resolved'),
  payload: z.object({
    hold_id: z.string(),
    resolution: z.string(),
    edited_text: z.string().nullable().optional(),
  }),
})

// Standoffs
const StandoffOpened = base.extend({
  type: z.literal('standoff_opened'),
  payload: z.object({
    standoff_id: z.string(),
    challenger: z.string(),
    defendant: z.string(),
    claim_ref: z.string(),
  }),
})

const StandoffTurn = base.extend({
  type: z.literal('standoff_turn'),
  payload: z.object({
    standoff_id: z.string(),
    turn_no: z.number().int().min(1).max(3),
    argument_summary: z.string(),
  }),
})

const StandoffResolved = base.extend({
  type: z.literal('standoff_resolved'),
  payload: z.object({
    standoff_id: z.string(),
    outcome: z.enum(['agreement', 'alpha_call', 'hold_opened']),
    rationale: z.string(),
  }),
})

// Stray detection
const StrayDetected = base.extend({
  type: z.literal('stray_detected'),
  payload: z.object({
    wolf_id: z.string(),
    pattern: z.enum(['repeat_fail', 'loop', 'timeout']),
    evidence_ref: z.string(),
  }),
})

const StrayRecovered = base.extend({
  type: z.literal('stray_recovered'),
  payload: z.object({
    wolf_id: z.string(),
    action: z.enum(['reroute', 'replan', 'respawn']),
    note_plain_english: z.string(),
  }),
})

// Doctor
const DoctorDispatched = base.extend({
  type: z.literal('doctor_dispatched'),
  payload: z.object({
    doctor_id: z.string(),
    target_wolf_id: z.string(),
    reason: z.string().nullable().optional(),
  }),
})

const DoctorHealed = base.extend({
  type: z.literal('doctor_healed'),
  payload: z.object({
    doctor_id: z.string(),
    target_wolf_id: z.string(),
    action: z.string().nullable().optional(),
    note_plain_english: z.string(),
  }),
})

// Boundary
const BoundaryWarning = base.extend({
  type: z.literal('boundary_warning'),
  payload: z.object({
    pct: z.number(),
    cumulative_usd: z.number(),
  }),
})

const BoundaryDowngrade = base.extend({
  type: z.literal('boundary_downgrade'),
  payload: z.object({
    wolf_id: z.string(),
    from_tier: z.enum(['max', 'plus', 'flash']),
    to_tier: z.enum(['max', 'plus', 'flash']),
    thinking_off: z.boolean(),
  }),
})

const BoundaryHalt = base.extend({
  type: z.literal('boundary_halt'),
  payload: z.object({
    checkpoint_id: z.string(),
    spend_breakdown: z.record(z.unknown()),
    resume_options: z.array(z.string()),
  }),
})

// Artifacts
const ArtifactCreated = base.extend({
  type: z.literal('artifact_created'),
  payload: z.object({
    artifact_id: z.string(),
    kind: z.enum(['draft', 'final', 'scorecard', 'transcript', 'md', 'html', 'pdf', 'docx', 'provenance_map', 'xlsx', 'pptx', 'png']),
    produced_by: z.string(),
    provenance_span_map_ref: z.string().nullable().optional(),
  }),
})

// Forge
const ForgeStarted = base.extend({
  type: z.literal('forge_started'),
  payload: z.object({ formats: z.array(z.string()) }),
})

const ForgeCompleted = base.extend({
  type: z.literal('forge_completed'),
  payload: z.object({
    formats: z.array(z.string()),
    artifact_ids: z.array(z.string()),
  }),
})

// Hunt terminal
const HuntCompleted = base.extend({
  type: z.literal('hunt_completed'),
  payload: z.object({
    final_artifact_id: z.string(),
    totals: z.record(z.unknown()),
  }),
})

const HuntFailed = base.extend({
  type: z.literal('hunt_failed'),
  payload: z.object({
    reason_plain_english: z.string(),
    partials_ref: z.string().nullable().optional(),
  }),
})

const HuntStopped = base.extend({
  type: z.literal('hunt_stopped'),
  payload: z.object({ by: z.literal('user') }),
})

// Benchmark
const BenchmarkStarted = base.extend({
  type: z.literal('benchmark_started'),
  payload: z.object({ lone_wolf_config: z.record(z.unknown()) }),
})

const BenchmarkCompleted = base.extend({
  type: z.literal('benchmark_completed'),
  payload: z.object({
    scorecard: z.object({
      lone_wolf: z.object({
        quality: z.number(),
        citations: z.number().int(),
        cost_usd: z.number(),
        time_s: z.number(),
        sources: z.number().int(),
      }),
      pack: z.object({
        quality: z.number(),
        citations: z.number().int(),
        cost_usd: z.number(),
        time_s: z.number(),
        sources: z.number().int(),
      }),
    }),
  }),
})

export const HuntEventSchema = z.discriminatedUnion('type', [
  HuntCreated, InputAdded, TranscriptReady,
  PlanProposed, PlanEdited, PlanApproved,
  WolfSpawned, StepStarted, StepCompleted, MessagePassed, WolfProgress,
  ToolCalled, ToolResult, TokensSpent,
  HoldOpened, HoldResolved,
  StandoffOpened, StandoffTurn, StandoffResolved,
  StrayDetected, StrayRecovered,
  DoctorDispatched, DoctorHealed,
  BoundaryWarning, BoundaryDowngrade, BoundaryHalt,
  ArtifactCreated,
  ForgeStarted, ForgeCompleted,
  HuntCompleted, HuntFailed, HuntStopped,
  BenchmarkStarted, BenchmarkCompleted,
])

export type HuntEvent = z.infer<typeof HuntEventSchema>

export type WolfRole = 'alpha' | 'beta' | 'scout' | 'tracker' | 'howler' | 'sentinel' | 'hunter' | 'elder' | 'doctor'
export type ModelTier = 'max' | 'plus' | 'flash'
export type WolfPhase = 'thinking' | 'searching' | 'reading' | 'merging' | 'writing' | 'critiquing' | 'forge'

export type WolfState = {
  wolf_id: string
  role: WolfRole
  model_tier: ModelTier
  thinking: boolean
  phase: WolfPhase | string | null
  last_text: string | null
  status: 'active' | 'done' | 'error' | 'strayed' | 'healing'
  cost_usd: number
  parent_wolf_id: string | null
}

export type BoundaryStatus = 'ok' | 'warn' | 'downgraded' | 'halted'

export type BoundaryState = {
  budget_usd: number
  spent_usd: number
  pct: number
  status: BoundaryStatus
  checkpoint_id: string | null
  resume_options: string[]
}

export type HoldState = {
  hold_id: string
  question: string
  options: string[]
  recommended: string
  context_ref: string | null
}

export type StandoffState = {
  standoff_id: string
  challenger: string
  defendant: string
  claim_ref: string
  turns: Array<{ turn_no: number; argument_summary: string }>
  outcome: 'agreement' | 'alpha_call' | 'hold_opened' | null
}

export type PlanState = {
  steps: unknown[]
  wolves: string[]
  pattern: 'sequential' | 'hierarchical' | 'parallel_then_merge' | 'standoff'
  assumptions: string[]
  est_cost: number
  est_time: number
  queries?: string[]
  strategy?: string
}

export type ArtifactRef = {
  artifact_id: string
  kind: string
  produced_by: string
}

export type HuntStatus =
  | 'idle'
  | 'planning'
  | 'plan_ready'
  | 'running'
  | 'hold'
  | 'standoff'
  | 'halted_boundary'
  | 'completed'
  | 'failed'
  | 'stopped'

export type HuntState = {
  hunt_id: string | null
  status: HuntStatus
  wolves: Record<string, WolfState>
  boundary: BoundaryState
  plan: PlanState | null
  holds: HoldState[]
  active_standoff: StandoffState | null
  artifacts: ArtifactRef[]
  final_artifact_id: string | null
  scorecard: { lone_wolf: unknown; pack: unknown } | null
  totals: Record<string, unknown> | null
  last_seq: number
}