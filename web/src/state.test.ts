import { describe, expect, it } from 'vitest'
import type { Action } from './state'
import { initialState, reduce } from './state'

describe('reduce', () => {
  it('merges resources by id across events', () => {
    let s = reduce(initialState, { type: 'resources', items: [{ id: 'vol-1', kind: 'ebs', size_gb: 50 }] })
    s = reduce(s, { type: 'resources', items: [{ id: 'vol-1', monthly_cost: 4 }] })
    s = reduce(s, { type: 'resources', items: [{ id: 'vol-1', blast_radius: 'safe', blast_warnings: ['listener HTTP:80 still configured'] }] })
    expect(s.resources['vol-1']).toEqual({
      id: 'vol-1', kind: 'ebs', size_gb: 50, monthly_cost: 4, blast_radius: 'safe',
      blast_warnings: ['listener HTTP:80 still configured'],
    })
  })

  it('ignores unknown action types instead of throwing', () => {
    const unknown = { type: 'not-a-real-event' } as unknown as Action
    expect(reduce(initialState, unknown)).toBe(initialState)
  })

  it('dedupes approvals and clears them on decided', () => {
    const a = { type: 'approval' as const, tool_call_id: 'c1', thread_id: 'main', tool: 'delete_volume', args: {}, resource_id: 'vol-1' }
    let s = reduce(reduce(initialState, a), a)
    expect(s.approvals).toHaveLength(1)
    s = reduce(s, { type: 'decided' })
    expect(s.approvals).toHaveLength(0)
  })

  it('upserts steps and messages, keeps order', () => {
    let s = reduce(initialState, { type: 'message', id: 'm1', content: 'Sca' })
    s = reduce(s, { type: 'message', id: 'm1', content: 'Scanning' })
    s = reduce(s, { type: 'step', id: 's1', kind: 'tool', title: 'list_unattached_volumes', detail: {} })
    expect(s.messages).toEqual({ m1: 'Scanning' })
    expect(s.feed).toEqual([{ kind: 'message', id: 'm1' }, { kind: 'step', id: 's1' }])
  })

  it('tracks status, error and output; reset clears everything', () => {
    let s = reduce(initialState, { type: 'status', status: 'error', message: 'boom' })
    expect(s.status).toBe('error'); expect(s.error).toBe('boom')
    s = reduce(s, { type: 'done', output: '## Summary' })
    expect(s.output).toBe('## Summary')
    expect(reduce(s, { type: 'reset' })).toEqual(initialState)
  })
})
