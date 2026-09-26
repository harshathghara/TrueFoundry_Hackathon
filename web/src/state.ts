import type { Approval, Resource, ServerEvent, Status, Step } from './types'

export interface FeedItem { kind: 'step' | 'message'; id: string }

export interface State {
  status: Status
  error?: string
  steps: Record<string, Step>
  messages: Record<string, string>
  feed: FeedItem[]
  resources: Record<string, Resource>
  approvals: Approval[]
  output?: string
}

export const initialState: State = { status: 'idle', steps: {}, messages: {}, feed: [], resources: {}, approvals: [] }

export type Action = ServerEvent | { type: 'reset' } | { type: 'decided' }

function addToFeed(feed: FeedItem[], item: FeedItem): FeedItem[] {
  return feed.some((f) => f.kind === item.kind && f.id === item.id) ? feed : [...feed, item]
}

export function reduce(s: State, a: Action): State {
  switch (a.type) {
    case 'reset':
      return initialState
    case 'decided':
      return { ...s, approvals: [] }
    case 'status':
      return { ...s, status: a.status, error: a.status === 'error' ? a.message : undefined }
    case 'step': {
      const step: Step = { id: a.id, kind: a.kind, title: a.title, detail: a.detail }
      return { ...s, steps: { ...s.steps, [a.id]: step }, feed: addToFeed(s.feed, { kind: 'step', id: a.id }) }
    }
    case 'message':
      return { ...s, messages: { ...s.messages, [a.id]: a.content }, feed: addToFeed(s.feed, { kind: 'message', id: a.id }) }
    case 'resources': {
      const resources = { ...s.resources }
      for (const r of a.items) resources[r.id] = { ...resources[r.id], ...r }
      return { ...s, resources }
    }
    case 'approval': {
      if (s.approvals.some((x) => x.tool_call_id === a.tool_call_id)) return s
      const approval: Approval = { tool_call_id: a.tool_call_id, thread_id: a.thread_id, tool: a.tool, args: a.args, resource_id: a.resource_id }
      return { ...s, approvals: [...s.approvals, approval] }
    }
    case 'done':
      return { ...s, output: a.output }
  }
}
