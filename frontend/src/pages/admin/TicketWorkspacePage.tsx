import { useCallback, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Alert, Button, ErrorState, PageSpinner, PriorityBadge, StatusBadge } from '../../components/ui'
import { api, type ApiError } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { useResource } from '../../lib/useResource'
import { useLiveRefetch } from '../../realtime/hooks'
import { AuditPanel } from './workspace/AuditPanel'
import { Composer } from './workspace/Composer'
import { ContextPanel } from './workspace/ContextPanel'
import { ControlsPanel } from './workspace/ControlsPanel'
import { ConversationPanel } from './workspace/ConversationPanel'
import { TriagePanel } from './workspace/TriagePanel'

const BackLink = () => (
  <Link to="/admin/tickets" className="text-sm font-medium text-indigo-600 hover:underline">← Ticket queue</Link>
)

function Workspace({ n }: { n: number }) {
  const { data, error, loading, reload } = useResource(`admin-ticket-${n}`, (s) => api.admin.ticket(n, s))
  useLiveRefetch(reload, { ticketNumber: n })
  const [actionError, setActionError] = useState<string | null>(null)

  const onChanged = useCallback(() => {
    setActionError(null)
    reload()
  }, [reload])

  const onError = useCallback(
    (err: ApiError) => {
      setActionError(err.message)
      if (err.status === 409) reload() // someone else changed the ticket: show the current state
    },
    [reload],
  )

  if (error && !data) {
    const missing = error.status === 404
    return (
      <div className="space-y-4">
        <ErrorState
          title={missing ? 'Ticket not found' : undefined}
          message={missing ? `There is no ticket TKT-${n}.` : error.message}
          onRetry={missing ? undefined : reload}
        />
        <BackLink />
      </div>
    )
  }
  if (loading || !data) return <PageSpinner />

  return (
    <>
      <BackLink />

      <div className="mb-5 mt-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-stone-900">{data.subject}</h1>
          <div className="flex items-center gap-2">
            <PriorityBadge priority={data.priority} />
            <StatusBadge status={data.status} />
          </div>
        </div>
        <p className="mt-1 text-sm text-stone-500">
          {data.display_id} · {data.category} · {data.author.name}
          {data.book ? ` · ${data.book.title}` : ' · General / Account Level'}
        </p>
        <p className="mt-0.5 text-xs text-stone-400">
          Opened {formatDateTime(data.created_at)} · Last updated {formatDateTime(data.updated_at)}
          {data.resolved_at ? ` · Resolved ${formatDateTime(data.resolved_at)}` : ''}
        </p>
      </div>

      {actionError && (
        <div className="mb-4 flex items-start gap-3">
          <div className="flex-1"><Alert tone="error">{actionError}</Alert></div>
          <Button variant="ghost" onClick={() => setActionError(null)}>Dismiss</Button>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-6">
          <ConversationPanel ticket={data} />
          <Composer key={data.ticket_number} ticket={data} onChanged={onChanged} onError={onError} />
        </div>
        <div className="space-y-6">
          <ControlsPanel ticket={data} onChanged={onChanged} onError={onError} />
          <TriagePanel ticket={data} onChanged={onChanged} onError={onError} />
          <ContextPanel ticket={data} />
          <AuditPanel ticket={data} />
        </div>
      </div>
    </>
  )
}

export function TicketWorkspacePage() {
  const { ticketNumber } = useParams()
  const n = Number(ticketNumber)
  if (!Number.isInteger(n) || n < 1) {
    return (
      <div className="space-y-4">
        <ErrorState title="Ticket not found" message="That ticket address isn't valid." />
        <BackLink />
      </div>
    )
  }
  return <Workspace n={n} />
}