import type { State } from '../state'

const badge: Record<string, string> = { tool: 'bg-sky-900 text-sky-200', sandbox: 'bg-violet-900 text-violet-200', subagent: 'bg-amber-900 text-amber-200' }

export function AgentFeed({ state }: { state: State }) {
  return (
    <div className="max-h-[28rem] space-y-2 overflow-y-auto rounded-xl border border-slate-800 bg-slate-900 p-3 text-sm">
      {state.feed.length === 0 && <div className="text-slate-500">Agent steps will stream here.</div>}
      {state.feed.map((f) => {
        if (f.kind === 'message') return <div key={`m-${f.id}`} className="whitespace-pre-wrap text-slate-300">{state.messages[f.id]}</div>
        const s = state.steps[f.id]
        return (
          <details key={`s-${f.id}`} className="rounded-lg bg-slate-950 p-2">
            <summary className="cursor-pointer">
              <span className={`mr-2 rounded px-1.5 py-0.5 text-xs ${badge[s.kind] ?? ''}`}>{s.kind}</span>{s.title}
            </summary>
            <pre className="mt-2 overflow-x-auto text-xs text-slate-400">{JSON.stringify(s.detail, null, 2)}</pre>
          </details>
        )
      })}
    </div>
  )
}
