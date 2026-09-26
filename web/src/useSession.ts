import { useCallback, useEffect, useReducer, useState } from 'react'
import { initialState, reduce } from './state'
import { sendDecisions, startScan, type DecisionInput } from './api'
import type { AuditEntry } from './types'

export function useSession() {
  const [state, dispatch] = useReducer(reduce, initialState)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [audit, setAudit] = useState<AuditEntry[]>([])

  useEffect(() => {
    if (!sessionId) return
    const es = new EventSource(`/api/sessions/${sessionId}/events`)
    es.onmessage = (m) => dispatch(JSON.parse(m.data))
    return () => es.close()
  }, [sessionId])

  const scan = useCallback(async (region: string) => {
    dispatch({ type: 'reset' })
    setAudit([])
    dispatch({ type: 'status', status: 'running' })
    try {
      setSessionId((await startScan(region)).session_id)
    } catch (e) {
      dispatch({ type: 'status', status: 'error', message: String(e) })
    }
  }, [])

  const decide = useCallback(async (decisions: DecisionInput[]) => {
    if (!sessionId) return false
    try {
      await sendDecisions(sessionId, decisions)
    } catch (e) {
      dispatch({ type: 'status', status: 'error', message: String(e) })
      return false
    }
    const at = new Date().toISOString()
    setAudit((prev) => [
      ...prev,
      ...decisions.map((d) => {
        const a = state.approvals.find((x) => x.tool_call_id === d.tool_call_id)
        return { at, tool: a?.tool ?? '?', resource_id: a?.resource_id ?? null, decision: d.allow ? 'approved' : 'denied', reason: d.reason } as AuditEntry
      }),
    ])
    dispatch({ type: 'decided' })
    return true
  }, [sessionId, state.approvals])

  return { state, audit, scan, decide }
}
