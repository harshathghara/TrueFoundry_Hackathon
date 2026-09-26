export type Status = 'idle' | 'running' | 'paused' | 'done' | 'error'

export interface Step { id: string; kind: 'tool' | 'sandbox' | 'message' | 'subagent'; title: string; detail: unknown }

export interface Resource {
  id: string
  kind?: 'ebs' | 'snapshot' | 'eip' | 'lb' | 'ec2_stopped'
  monthly_cost?: number
  blast_radius?: string
  age_days?: number
  size_gb?: number
  name?: string
  tags?: Record<string, string>
}

export interface Approval { tool_call_id: string; thread_id: string; tool: string; args: Record<string, unknown>; resource_id: string | null }

export interface AuditEntry { at: string; tool: string; resource_id: string | null; decision: 'approved' | 'denied'; reason?: string }

export type ServerEvent =
  | { type: 'status'; status: Status; message?: string }
  | ({ type: 'step' } & Step)
  | { type: 'message'; id: string; content: string }
  | ({ type: 'approval' } & Approval)
  | { type: 'resources'; items: Resource[] }
  | { type: 'done'; output: string }
