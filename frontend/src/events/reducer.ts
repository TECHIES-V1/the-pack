import type { HuntEvent, HuntState, WolfState } from './schema'

export const initialHuntState: HuntState = {
  hunt_id: null,
  status: 'idle',
  wolves: {},
  boundary: {
    budget_usd: 0,
    spent_usd: 0,
    pct: 0,
    status: 'ok',
    checkpoint_id: null,
    resume_options: [],
  },
  plan: null,
  holds: [],
  active_standoff: null,
  artifacts: [],
  final_artifact_id: null,
  scorecard: null,
  totals: null,
  last_seq: -1,
}

function setWolf(state: HuntState, wolf_id: string, patch: Partial<WolfState>): HuntState {
  const existing = state.wolves[wolf_id]
  if (!existing) return state
  return {
    ...state,
    wolves: { ...state.wolves, [wolf_id]: { ...existing, ...patch } },
  }
}

export function huntReducer(state: HuntState, event: HuntEvent): HuntState {
  const next = { ...state, last_seq: Math.max(state.last_seq, event.seq) }

  switch (event.type) {
    case 'hunt_created':
      return { ...next, hunt_id: event.hunt_id, status: 'planning' }

    case 'input_added':
      return next

    case 'transcript_ready':
      return next

    case 'plan_proposed':
      return {
        ...next,
        status: 'plan_ready',
        plan: {
          steps: event.payload.steps,
          wolves: event.payload.wolves,
          pattern: event.payload.pattern,
          assumptions: event.payload.assumptions,
          est_cost: event.payload.est_cost,
          est_time: event.payload.est_time,
          queries: event.payload.queries,
          strategy: event.payload.strategy,
        },
      }

    case 'plan_edited':
      return next

    case 'plan_approved':
      return {
        ...next,
        status: 'running',
        boundary: {
          ...next.boundary,
          budget_usd: event.payload.boundary_usd,
        },
      }

    case 'wolf_spawned':
      return {
        ...next,
        wolves: {
          ...next.wolves,
          [event.payload.wolf_id]: {
            wolf_id: event.payload.wolf_id,
            role: event.payload.role,
            model_tier: event.payload.model_tier,
            thinking: event.payload.thinking,
            phase: null,
            last_text: null,
            status: 'active',
            cost_usd: 0,
            parent_wolf_id: event.payload.parent_wolf_id ?? null,
          },
        },
      }

    case 'step_started':
      return setWolf(next, event.payload.wolf_id, { status: 'active' })

    case 'step_completed':
      return setWolf(next, event.payload.wolf_id, { status: 'done', phase: null })

    case 'message_passed':
      return next

    case 'wolf_progress':
      return setWolf(next, event.payload.wolf_id, {
        phase: event.payload.phase,
        last_text: event.payload.text,
      })

    case 'tool_called':
      return setWolf(next, event.payload.wolf_id, { phase: event.payload.tool })

    case 'tool_result':
      return next

    case 'tokens_spent': {
      const cost = event.payload.cost_usd
      const spent = next.boundary.spent_usd + cost
      const pct = next.boundary.budget_usd > 0 ? spent / next.boundary.budget_usd : 0
      const wolf = next.wolves[event.payload.wolf_id]
      return {
        ...next,
        boundary: { ...next.boundary, spent_usd: spent, pct },
        wolves: wolf
          ? { ...next.wolves, [event.payload.wolf_id]: { ...wolf, cost_usd: wolf.cost_usd + cost } }
          : next.wolves,
      }
    }

    case 'hold_opened':
      return {
        ...next,
        status: 'hold',
        holds: [
          ...next.holds,
          {
            hold_id: event.payload.hold_id,
            question: event.payload.question,
            options: event.payload.options,
            recommended: event.payload.recommended,
            context_ref: event.payload.context_ref ?? null,
          },
        ],
      }

    case 'hold_resolved':
      return {
        ...next,
        status: next.holds.length > 1 ? 'hold' : (next.active_standoff ? 'standoff' : 'running'),
        holds: next.holds.filter((h) => h.hold_id !== event.payload.hold_id),
      }

    case 'standoff_opened':
      return {
        ...next,
        status: 'standoff',
        active_standoff: {
          standoff_id: event.payload.standoff_id,
          challenger: event.payload.challenger,
          defendant: event.payload.defendant,
          claim_ref: event.payload.claim_ref,
          turns: [],
          outcome: null,
        },
      }

    case 'standoff_turn':
      if (!next.active_standoff) return next
      return {
        ...next,
        active_standoff: {
          ...next.active_standoff,
          turns: [
            ...next.active_standoff.turns,
            { turn_no: event.payload.turn_no, argument_summary: event.payload.argument_summary },
          ],
        },
      }

    case 'standoff_resolved':
      return {
        ...next,
        status: event.payload.outcome === 'hold_opened' ? 'hold' : 'running',
        active_standoff: next.active_standoff
          ? { ...next.active_standoff, outcome: event.payload.outcome }
          : null,
      }

    case 'stray_detected':
      return setWolf(next, event.payload.wolf_id, { status: 'strayed' })

    case 'stray_recovered':
      return setWolf(next, event.payload.wolf_id, { status: 'active' })

    case 'doctor_dispatched':
      return setWolf(next, event.payload.target_wolf_id, { status: 'healing' })

    case 'doctor_healed':
      return setWolf(next, event.payload.target_wolf_id, { status: 'active' })

    case 'boundary_warning':
      return {
        ...next,
        boundary: {
          ...next.boundary,
          status: 'warn',
          pct: event.payload.pct,
          spent_usd: event.payload.cumulative_usd,
        },
      }

    case 'boundary_downgrade': {
      const wolf = next.wolves[event.payload.wolf_id]
      return {
        ...next,
        boundary: { ...next.boundary, status: 'downgraded' },
        wolves: wolf
          ? {
              ...next.wolves,
              [event.payload.wolf_id]: {
                ...wolf,
                model_tier: event.payload.to_tier,
                thinking: !event.payload.thinking_off,
              },
            }
          : next.wolves,
      }
    }

    case 'boundary_halt':
      return {
        ...next,
        status: 'halted_boundary',
        boundary: {
          ...next.boundary,
          status: 'halted',
          checkpoint_id: event.payload.checkpoint_id,
          resume_options: event.payload.resume_options,
        },
      }

    case 'artifact_created':
      return {
        ...next,
        artifacts: [
          ...next.artifacts,
          {
            artifact_id: event.payload.artifact_id,
            kind: event.payload.kind,
            produced_by: event.payload.produced_by,
          },
        ],
      }

    case 'forge_started':
      return next

    case 'forge_completed':
      return next

    case 'hunt_completed':
      return {
        ...next,
        status: 'completed',
        final_artifact_id: event.payload.final_artifact_id,
        totals: event.payload.totals as Record<string, unknown>,
      }

    case 'hunt_failed':
      return { ...next, status: 'failed' }

    case 'hunt_stopped':
      return { ...next, status: 'stopped' }

    case 'benchmark_started':
      return next

    case 'benchmark_completed':
      return { ...next, scorecard: event.payload.scorecard }

    default: {
      const _exhaustive: never = event
      void _exhaustive
      return state
    }
  }
}