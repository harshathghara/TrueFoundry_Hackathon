import type { AuditEntry } from '../types'

export function AuditTrail({ audit }: { audit: AuditEntry[] }) {
  if (audit.length === 0) return null
  return (
    <ul className="space-y-1 rounded-xl border border-slate-800 bg-slate-900 p-3 text-sm">
      {audit.map((a, i) => (
        <li key={i}>
          <span className="text-slate-500">{a.at}</span> · <b className={a.decision === 'approved' ? 'text-emerald-400' : 'text-rose-400'}>{a.decision}</b> · {a.tool} {a.resource_id}
          {a.reason && <span className="text-slate-400"> — "{a.reason}"</span>}
        </li>
      ))}
    </ul>
  )
}
