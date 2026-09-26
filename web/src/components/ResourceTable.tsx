import type { Resource } from '../types'

export function ResourceTable({ resources }: { resources: Resource[] }) {
  const rows = resources.filter((r) => r.kind).sort((a, b) => (b.monthly_cost ?? 0) - (a.monthly_cost ?? 0))
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-900 text-slate-400">
          <tr><th className="p-2">Kind</th><th className="p-2">Resource</th><th className="p-2">$/mo</th><th className="p-2">Age</th><th className="p-2">Blast radius</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t border-slate-800">
              <td className="p-2">{r.kind}</td>
              <td className="p-2 font-mono text-xs">{r.name ?? r.tags?.Name ?? r.id}</td>
              <td className="p-2">{r.monthly_cost != null ? `$${r.monthly_cost.toFixed(2)}` : '—'}</td>
              <td className="p-2">{r.age_days != null ? `${r.age_days}d` : '—'}</td>
              <td className={`p-2 ${r.blast_radius && r.blast_radius !== 'safe' ? 'text-rose-400' : 'text-emerald-400'}`}>{r.blast_radius ?? '—'}</td>
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={5} className="p-3 text-slate-500">No resources yet.</td></tr>}
        </tbody>
      </table>
    </div>
  )
}
