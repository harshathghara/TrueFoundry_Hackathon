import { useEffect, useState } from 'react'
import { getHealth } from '../api'
import type { Status } from '../types'

export function ScanPanel({ status, error, onScan }: { status: Status; error?: string; onScan: (region: string) => void }) {
  const [region, setRegion] = useState('us-east-1')
  const [health, setHealth] = useState<{ trueforge: boolean; mcp: boolean } | null>(null)
  useEffect(() => { getHealth().then(setHealth).catch(() => setHealth({ trueforge: false, mcp: false })) }, [])
  const ready = health?.trueforge && health?.mcp
  const busy = status === 'running'
  return (
    <div className="flex flex-wrap items-center gap-3">
      <select value={region} onChange={(e) => setRegion(e.target.value)} className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2">
        {['us-east-1', 'us-west-2', 'ap-south-1', 'eu-west-1'].map((r) => <option key={r}>{r}</option>)}
      </select>
      <button disabled={!ready || busy} onClick={() => onScan(region)}
        className="rounded-lg bg-emerald-600 px-4 py-2 font-medium hover:bg-emerald-500 disabled:opacity-40">
        {busy ? 'Janitor running…' : 'Run janitor'}
      </button>
      <span className="text-sm text-slate-400">
        TrueForge {health?.trueforge ? '🟢' : '🔴'} · MCP {health?.mcp ? '🟢' : '🔴'} · status: <b>{status}</b>
      </span>
      {error && <span className="text-sm text-rose-400">{error}</span>}
    </div>
  )
}
