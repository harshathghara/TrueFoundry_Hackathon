import { useState } from 'react'
import type { DecisionInput } from '../api'
import type { Approval, Resource, Status } from '../types'

export function ApprovalCards({ approvals, resources, status, onSubmit }: {
  approvals: Approval[]; resources: Record<string, Resource>; status: Status; onSubmit: (d: DecisionInput[]) => void
}) {
  const [choice, setChoice] = useState<Record<string, { allow: boolean; reason: string }>>({})
  if (approvals.length === 0) return null
  const all = approvals.every((a) => choice[a.tool_call_id])
  const canSubmit = all && status === 'paused'
  const set = (id: string, allow: boolean) => setChoice((c) => ({ ...c, [id]: { allow, reason: c[id]?.reason ?? '' } }))
  return (
    <div className="space-y-3 rounded-xl border-2 border-amber-500 bg-amber-950/30 p-4">
      <h2 className="text-lg font-semibold text-amber-300">⏸ Agent paused — irreversible actions need your approval</h2>
      {approvals.map((a) => {
        const r = a.resource_id ? resources[a.resource_id] : undefined
        const c = choice[a.tool_call_id]
        return (
          <div key={a.tool_call_id} className="rounded-lg border border-slate-700 bg-slate-900 p-3">
            <div className="font-mono text-sm"><b className="text-rose-300">{a.tool}</b> {a.resource_id}</div>
            <div className="mt-1 text-sm text-slate-300">
              Cost: <b>{r?.monthly_cost != null ? `$${r.monthly_cost.toFixed(2)}/mo` : 'unknown'}</b> · Blast radius: <b>{r?.blast_radius ?? 'not checked'}</b>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <button onClick={() => set(a.tool_call_id, true)} className={`rounded px-3 py-1 ${c?.allow === true ? 'bg-emerald-600' : 'bg-slate-700'}`}>Approve</button>
              <button onClick={() => set(a.tool_call_id, false)} className={`rounded px-3 py-1 ${c?.allow === false ? 'bg-rose-600' : 'bg-slate-700'}`}>Deny</button>
              {c?.allow === false && (
                <input placeholder="reason" value={c.reason} className="flex-1 rounded bg-slate-800 px-2 py-1 text-sm"
                  onChange={(e) => setChoice((x) => ({ ...x, [a.tool_call_id]: { allow: false, reason: e.target.value } }))} />
              )}
            </div>
          </div>
        )
      })}
      <button disabled={!canSubmit} className="rounded-lg bg-amber-500 px-4 py-2 font-medium text-slate-950 disabled:opacity-40"
        onClick={() => onSubmit(approvals.map((a) => ({ tool_call_id: a.tool_call_id, thread_id: a.thread_id, allow: choice[a.tool_call_id].allow, reason: choice[a.tool_call_id].reason || undefined })))}>
        Submit decisions
      </button>
    </div>
  )
}
