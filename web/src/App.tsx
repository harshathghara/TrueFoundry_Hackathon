import { AgentFeed } from './components/AgentFeed'
import { ApprovalCards } from './components/ApprovalCards'
import { AuditTrail } from './components/AuditTrail'
import { KpiStrip } from './components/KpiStrip'
import { PlanView } from './components/PlanView'
import { ResourceTable } from './components/ResourceTable'
import { ScanPanel } from './components/ScanPanel'
import { useSession } from './useSession'

export default function App() {
  const { state, audit, scan, decide, submitError } = useSession()
  const resources = Object.values(state.resources)
  return (
    <main className="mx-auto max-w-7xl space-y-5 p-4 md:p-8">
      <header>
        <h1 className="text-3xl font-bold">🧹 Cloud Cost Janitor</h1>
        <p className="text-slate-400">Finds idle AWS spend, plans the teardown in a sandbox, and deletes nothing without your approval. Powered by TrueForge.</p>
      </header>
      <ScanPanel status={state.status} error={state.error} onScan={scan} />
      <KpiStrip resources={resources} audit={audit} pending={state.approvals.length} />
      <ApprovalCards approvals={state.approvals} resources={state.resources} status={state.status} submitError={submitError} onSubmit={decide} />
      <div className="grid gap-5 lg:grid-cols-2">
        <section><h2 className="mb-2 font-semibold">Idle resources</h2><ResourceTable resources={resources} /></section>
        <section><h2 className="mb-2 font-semibold">Agent steps</h2><AgentFeed state={state} /></section>
      </div>
      <section><h2 className="mb-2 font-semibold">Report</h2><PlanView output={state.output} /></section>
      <section><h2 className="mb-2 font-semibold">Audit trail</h2><AuditTrail audit={audit} /></section>
    </main>
  )
}
