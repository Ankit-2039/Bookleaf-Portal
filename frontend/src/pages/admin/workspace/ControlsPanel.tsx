import { useState } from 'react'
import { useAuth } from '../../../auth/useAuth'
import { Alert, Button, Card, Select, StatusBadge } from '../../../components/ui'
import { api, toApiError, type ApiError } from '../../../lib/api'
import { ALLOWED_TRANSITIONS } from '../../../lib/constants'
import type { AdminTicketDetail, TicketPatchBody, TicketStatus } from '../../../lib/types'
import { useResource } from '../../../lib/useResource'

interface Props { ticket: AdminTicketDetail; onChanged: () => void; onError: (e: ApiError) => void }

function actionLabel(from: TicketStatus, to: TicketStatus): string {
  if (to === 'Resolved') return 'Mark resolved'
  if (to === 'Closed') return 'Close ticket'
  if (to === 'Open') return 'Move back to Open'
  return from === 'Resolved' ? 'Reopen' : 'Mark in progress'
}

export function ControlsPanel({ ticket, onChanged, onError }: Props) {
  const { user } = useAuth()
  const admins = useResource('admin-admins', (s) => api.admin.admins(s))
  const [busy, setBusy] = useState(false)
  const [confirmClose, setConfirmClose] = useState(false)

  async function patch(body: TicketPatchBody) {
    setBusy(true)
    try {
      await api.admin.patchTicket(ticket.ticket_number, body)
      setConfirmClose(false)
      onChanged()
    } catch (e) {
      onError(toApiError(e))
    } finally {
      setBusy(false)
    }
  }

  const targets = ALLOWED_TRANSITIONS[ticket.status]
  const mine = ticket.assignee?.id === user?.id

  // Make sure the current assignee is selectable even if they are not in the active-admin list.
  const options = [...(admins.data ?? [])]
  if (ticket.assignee && !options.some((a) => a.id === ticket.assignee!.id)) options.push(ticket.assignee)

  return (
    <Card className="space-y-4 p-4">
      <div>
        <h2 className="mb-2 font-semibold text-stone-900">Status</h2>
        <div className="mb-3"><StatusBadge status={ticket.status} /></div>
        {targets.length === 0 ? (
          <p className="text-sm text-stone-500">This ticket is closed and can't be changed.</p>
        ) : confirmClose ? (
          <Alert tone="warning">
            <p className="mb-2">Closing is final: the ticket can't be reopened or replied to.</p>
            <div className="flex gap-2">
              <Button variant="danger" loading={busy} onClick={() => void patch({ status: 'Closed' })}>Yes, close it</Button>
              <Button variant="secondary" disabled={busy} onClick={() => setConfirmClose(false)}>Cancel</Button>
            </div>
          </Alert>
        ) : (
          <div className="flex flex-wrap gap-2">
            {targets.map((t) => (
              <Button
                key={t}
                variant="secondary"
                disabled={busy}
                onClick={() => (t === 'Closed' ? setConfirmClose(true) : void patch({ status: t }))}
              >
                {actionLabel(ticket.status, t)}
              </Button>
            ))}
          </div>
        )}
      </div>

      <div className="border-t border-stone-100 pt-4">
        <h2 className="mb-2 font-semibold text-stone-900">Assignee</h2>
        <Select
          aria-label="Assignee"
          value={ticket.assignee?.id ?? ''}
          disabled={busy}
          onChange={(e) => void patch({ assignee_id: e.target.value || null })}
        >
          <option value="">Unassigned</option>
          {options.map((a) => (
            <option key={a.id} value={a.id}>{a.name}{a.id === user?.id ? ' (me)' : ''}</option>
          ))}
        </Select>
        {!mine && (
          <div className="mt-2">
            <Button variant="secondary" disabled={busy} onClick={() => void patch({ assignee_id: 'me' })}>Assign to me</Button>
          </div>
        )}
      </div>
    </Card>
  )
}