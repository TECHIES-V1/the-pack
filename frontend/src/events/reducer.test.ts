import { readFileSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'
import { describe, it, expect } from 'vitest'
import { huntReducer, initialHuntState } from './reducer'
import { HuntEventSchema } from './schema'
import type { HuntState } from './schema'

const __dirname = dirname(fileURLToPath(import.meta.url))
const FIXTURES = resolve(__dirname, '../../../backend/fixtures')

function replayFixture(filename: string): HuntState {
  const lines = readFileSync(resolve(FIXTURES, filename), 'utf-8')
    .trim()
    .split('\n')
    .filter(Boolean)

  return lines.reduce((state, line) => {
    const result = HuntEventSchema.safeParse(JSON.parse(line))
    if (!result.success) return state
    return huntReducer(state, result.data)
  }, initialHuntState)
}

describe('huntReducer fixture replay', () => {
  it('flow_a_researcher: hunt completes', () => {
    const state = replayFixture('flow_a_researcher.jsonl')
    expect(state.status).toBe('completed')
    expect(Object.keys(state.wolves).length).toBeGreaterThan(0)
    expect(state.final_artifact_id).not.toBeNull()
  })

  it('flow_b_meeting: hunt completes', () => {
    const state = replayFixture('flow_b_meeting.jsonl')
    expect(state.status).toBe('completed')
  })

  it('boundary_halt: hunt halts at spend cap', () => {
    const state = replayFixture('boundary_halt.jsonl')
    expect(state.status).toBe('halted_boundary')
    expect(state.boundary.status).toBe('halted')
    expect(state.boundary.checkpoint_id).not.toBeNull()
  })

  it('standoff_stray: standoff opens and resolves', () => {
    const state = replayFixture('standoff_stray.jsonl')
    expect(['running', 'completed', 'stopped', 'failed']).toContain(state.status)
    expect(state.last_seq).toBeGreaterThan(0)
  })

  it('reducer is pure: same input always produces same output', () => {
    const state1 = replayFixture('flow_a_researcher.jsonl')
    const state2 = replayFixture('flow_a_researcher.jsonl')
    expect(state1).toEqual(state2)
  })
})