import Markdown from 'react-markdown'

export function PlanView({ output }: { output?: string }) {
  if (!output) return null
  return <div className="prose prose-invert max-w-none rounded-xl border border-slate-800 bg-slate-900 p-4"><Markdown>{output}</Markdown></div>
}
