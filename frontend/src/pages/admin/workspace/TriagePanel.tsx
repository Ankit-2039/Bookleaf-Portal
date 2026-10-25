import { useState } from 'react'
import { Alert, Button, Card, Field, Select } from '../../../components/ui'
import { api, toApiError, type ApiError } from '../../../lib/api'
import { CATEGORIES, PRIORITIES } from '../../../lib/constants'
import type { AdminTicketDetail, TicketCategory, TicketPriority } from '../../../lib/types'

interface Props { ticket: AdminTicketDetail; onChanged: () => void; onError: (e: ApiError) => void }

const AI_ERRORS: Record<string, string> = {
  ai_not_configured: 'AI is not configured on the server.',
  ai_rate_limited: 'The AI service was busy (rate limit).',
  ai_timeout: 'The AI service timed out.',
  ai_unavailable: 'The AI service was unavailable.',
  ai_bad_output: 'The AI returned an answer that could not be used.',
  ai_auth_failed: 'The AI service rejected the server credentials.',
  ai_misconfigured: 'The AI service is not configured correctly.',
  ai_truncated: 'The AI ran out of room before finishing.',
  ai_empty_response: 'The AI returned an empty answer.',
}

export function TriagePanel({ ticket, onChanged, onError }: Props) {
  const [busy, setBusy] = useState(false)
  const ai = ticket.ai

  async function run(action: () => Promise<unknown>) {
    setBusy(true)
    try {
      await action()
      onChanged()
    } catch (e) {
      onError(toApiError(e))
    } finally {
      setBusy(false)
    }
  }

  const setCategory = (category: TicketCategory) => run(() => api.admin.patchTicket(ticket.ticket_number, { category }))
  const setPriority = (priority: TicketPriority) => run(() => api.admin.patchTicket(ticket.ticket_number, { priority }))

  return (
    <Card className="space-y-4 p-4">
      <h2 className="font-semibold text-stone-900">Classification</h2>

      {ticket.classification_status === 'pending' && <Alert tone="info">AI triage is running. This updates by itself.</Alert>}
      {ticket.classification_status === 'failed' && (
        <Alert tone="warning">
          AI triage failed{ai.error_code ? `: ${AI_ERRORS[ai.error_code] ?? 'the AI step failed.'}` : '.'} Set the category and
          priority yourself, or re-run it below.
        </Alert>
      )}

      <Field label="Category" htmlFor="category">
        <Select
          id="category"
          value={ticket.category}
          disabled={busy}
          onChange={(e) => void setCategory(e.target.value as TicketCategory)}
        >
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </Select>
        <div className="flex flex-wrap items-center gap-x-3 text-xs">
          {ticket.category_overridden && <span className="text-indigo-600">Edited by admin</span>}
          {ai.ai_category && (
            <span className="text-stone-500">AI suggested: {ai.ai_category}</span>
          )}
          {ai.ai_category && ai.ai_category !== ticket.category && (
            <button type="button" disabled={busy} onClick={() => void setCategory(ai.ai_category!)} className="font-medium text-indigo-600 hover:underline disabled:opacity-50">
              Use AI suggestion
            </button>
          )}
        </div>
      </Field>

      <Field label="Priority" htmlFor="priority">
        <Select
          id="priority"
          value={ticket.priority}
          disabled={busy}
          onChange={(e) => void setPriority(e.target.value as TicketPriority)}
        >
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </Select>
        <div className="flex flex-wrap items-center gap-x-3 text-xs">
          {ticket.priority_overridden && <span className="text-indigo-600">Edited by admin</span>}
          {ai.ai_priority && <span className="text-stone-500">AI suggested: {ai.ai_priority}</span>}
          {ai.ai_priority && ai.ai_priority !== ticket.priority && (
            <button type="button" disabled={busy} onClick={() => void setPriority(ai.ai_priority!)} className="font-medium text-indigo-600 hover:underline disabled:opacity-50">
              Use AI suggestion
            </button>
          )}
        </div>
      </Field>

      {ai.ai_rationale && (
        <div className="rounded-md bg-stone-50 p-3 text-xs text-stone-600">
          <p>{ai.ai_rationale}</p>
          <p className="mt-1 text-stone-400">AI suggestions are advisory. Review them before relying on them.</p>
        </div>
      )}

      <div>
        <Button variant="secondary" loading={busy} onClick={() => void run(() => api.admin.retriage(ticket.ticket_number))}>
          Re-run AI triage
        </Button>
        <p className="mt-1 text-xs text-stone-500">Fields you've edited are never overwritten.</p>
      </div>
    </Card>
  )
}