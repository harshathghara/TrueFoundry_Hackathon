export interface DecisionInput { tool_call_id: string; thread_id: string; allow: boolean; reason?: string }

async function post<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`)
  return r.json()
}

export const startScan = (region: string) => post<{ session_id: string }>('/api/scan', { region })
export const sendDecisions = (sessionId: string, decisions: DecisionInput[]) =>
  post<{ ok: boolean }>(`/api/sessions/${sessionId}/decisions`, { decisions })
export const getHealth = async () => (await fetch('/api/health')).json() as Promise<{ trueforge: boolean; mcp: boolean }>
