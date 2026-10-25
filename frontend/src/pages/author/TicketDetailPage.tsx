import { Link, useLocation, useParams } from 'react-router-dom'
import { LinkButton } from '../../components/LinkButton'
import { Alert, Card, ErrorState, PageSpinner, PriorityBadge, StatusBadge } from '../../components/ui'
import { api } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/format'
import { useResource } from '../../lib/useResource'
import { useLiveRefetch } from '../../realtime/hooks'

function Bubble({ mine, label, at, body }: { mine: boolean; label: string; at: string; body: string }) {
  return (
    <div className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-lg px-4 py-3 text-sm shadow-sm ring-1 ${
          mine ? 'bg-emerald-50 ring-emerald-200' : 'bg-white ring-stone-200'
        }`}
      >
        <p className="mb-1 text-xs font-medium text-stone-500">
          {label} · {formatDateTime(at)}
        </p>
        <p className="whitespace-pre-wrap break-words text-stone-900">{body}</p>
      </div>
    </div>
  )
}

function TicketView({ n }: { n: number }) {
  const location = useLocation()
  const justCreated = (location.state as { created?: boolean } | null)?.created === true

  const { data, error, loading, reload } = useResource(`author-ticket-${n}`, (s) => api.author.ticket(n, s))
  useLiveRefetch(reload, { ticketNumber: n })

  if (error && !data) {
    return (
      <div className="space-y-4">
        <ErrorState
          title={error.status === 404 ? 'Ticket not found' : undefined}
          message={error.status === 404 ? "We couldn't find that ticket on your account." : error.message}
          onRetry={error.status === 404 ? undefined : reload}
        />
        <Link to="/author/tickets" className="text-sm font-medium text-emerald-700 hover:underline">← Back to My Tickets</Link>
      </div>
    )
  }
  if (loading || !data) return <PageSpinner />

  const closedOrResolved = data.status === 'Resolved' || data.status === 'Closed'
  const followUp = data.book ? `/author/tickets/new?book=${data.book.id}` : '/author/tickets/new'

  return (
    <>
      <Link to="/author/tickets" className="text-sm font-medium text-emerald-700 hover:underline">← My Tickets</Link>

      {justCreated && (
        <div className="mt-3">
          <Alert tone="success">Your query was submitted. Replies from our team will appear on this page automatically.</Alert>
        </div>
      )}

      <div className="mb-5 mt-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-stone-900">{data.subject}</h1>
          <div className="flex items-center gap-2">
            <PriorityBadge priority={data.priority} />
            <StatusBadge status={data.status} />
          </div>
        </div>
        <p className="mt-1 text-sm text-stone-500">
          {data.display_id} · {data.book?.title ?? 'General / Account Level'} · {data.category}
        </p>
        <p className="mt-0.5 text-xs text-stone-400">
          Opened {formatDate(data.created_at)} · Last updated {formatDateTime(data.updated_at)}
        </p>
      </div>

      <div className="space-y-3" role="log" aria-live="polite" aria-label="Conversation">
        <Bubble mine label="You" at={data.created_at} body={data.description} />
        {data.messages.map((m) => (
          <Bubble key={m.id} mine={!m.from_support} label={m.sender_label} at={m.created_at} body={m.body} />
        ))}
      </div>

      {data.messages.length === 0 && (
        <div className="mt-4">
          <Alert tone="info">Our team hasn't replied yet. Replies appear here automatically, so there's no need to refresh.</Alert>
        </div>
      )}

      <Card className="mt-6 flex flex-wrap items-center justify-between gap-3 p-4">
        <p className="text-sm text-stone-600">
          {closedOrResolved
            ? `This ticket is ${data.status.toLowerCase()}. If something is still not right, you can raise a follow-up.`
            : 'Need to add something? Raise a follow-up query and we will link it to your account.'}
        </p>
        <LinkButton to={followUp}>Raise a follow-up query</LinkButton>
      </Card>
    </>
  )
}

export function TicketDetailPage() {
  const { ticketNumber } = useParams()
  const n = Number(ticketNumber)
  if (!Number.isInteger(n) || n < 1) {
    return (
      <div className="space-y-4">
        <ErrorState title="Ticket not found" message="That ticket address isn't valid." />
        <Link to="/author/tickets" className="text-sm font-medium text-emerald-700 hover:underline">← Back to My Tickets</Link>
      </div>
    )
  }
  return <TicketView n={n} />
}