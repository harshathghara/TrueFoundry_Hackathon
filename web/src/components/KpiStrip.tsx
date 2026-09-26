import type { AuditEntry, Resource } from '../types'

const usd = (n: number) => `$${n.toFixed(2)}`

export function KpiStrip({ resources, audit, pending }: { resources: Resource[]; audit: AuditEntry[]; pending: number }) {
  const waste = resources.reduce((t, r) => t + (r.monthly_cost ?? 0), 0)
  const byId = Object.fromEntries(resources.map((r) => [r.id, r]))
  const saved = audit.filter((a) => a.decision === 'approved').reduce((t, a) => t + (byId[a.resource_id ?? '']?.monthly_cost ?? 0), 0)
  const tiles = [
    ['Idle resources', String(resources.filter((r) => r.kind).length)],
    ['Monthly waste', usd(waste)],
    ['Approved savings / mo', usd(saved)],
    ['Pending approvals', String(pending)],
  ]
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {tiles.map(([label, value]) => (
        <div key={label} className="rounded-xl border border-slate-800 bg-slate-900 p-4">
          <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
          <div className="mt-1 text-2xl font-semibold">{value}</div>
        </div>
      ))}
    </div>
  )
}
