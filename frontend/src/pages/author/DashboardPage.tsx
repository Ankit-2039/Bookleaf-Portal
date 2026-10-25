import { useAuth } from '../../auth/useAuth'
import { LinkButton } from '../../components/LinkButton'
import { Card, EmptyState, ErrorState, PageHeader, PageSpinner, StatCard, StatusBadge } from '../../components/ui'
import { api } from '../../lib/api'
import { STATUSES } from '../../lib/constants'
import { formatINR } from '../../lib/format'
import { useResource } from '../../lib/useResource'
import { useLiveRefetch } from '../../realtime/hooks'
import { TicketListRow } from './TicketListRow'

export function DashboardPage() {
  const { user } = useAuth()
  const stats = useResource('author-dashboard', (s) => api.author.dashboard(s))
  const recent = useResource('author-recent-tickets', (s) => api.author.tickets({ page_size: 5 }, s))

  useLiveRefetch(() => {
    stats.reload()
    recent.reload()
  })

  if (stats.error && !stats.data) return <ErrorState message={stats.error.message} onRetry={stats.reload} />
  if (!stats.data) return <PageSpinner />

  const d = stats.data
  const firstName = user?.name.split(' ')[0] ?? ''

  return (
    <>
      <PageHeader
        title={`Welcome back, ${firstName}`}
        subtitle="Your books, royalties and support queries in one place."
        actions={<LinkButton to="/author/tickets/new">Submit a query</LinkButton>}
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Total books" value={d.total_books} />
        <StatCard label="Published" value={d.published_books} />
        <StatCard label="In production" value={d.books_in_production} />
        <StatCard label="Open tickets" value={d.open_tickets} hint="Open + In Progress" />
      </div>

      <h2 className="mb-3 mt-8 text-lg font-semibold text-stone-900">Royalties</h2>
      {d.total_books === 0 ? (
        <EmptyState title="No books on your account yet" description="Once your first book is added, your sales and royalty figures will appear here." />
      ) : (
        <Card className="p-5">
          <dl className="grid gap-4 sm:grid-cols-3">
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-stone-500">Total earned</dt>
              <dd className="mt-1 text-2xl font-semibold text-stone-900">{formatINR(d.total_royalty_earned)}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-stone-500">Paid</dt>
              <dd className="mt-1 text-2xl font-semibold text-emerald-700">{formatINR(d.royalty_paid)}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-stone-500">Pending</dt>
              <dd className={`mt-1 text-2xl font-semibold ${d.royalty_pending > 0 ? 'text-amber-700' : 'text-stone-900'}`}>
                {formatINR(d.royalty_pending)}
              </dd>
            </div>
          </dl>
          <p className="mt-4 border-t border-stone-100 pt-3 text-xs text-stone-500">
            Royalties are calculated quarterly and paid within 45 days of the quarter ending. Balances under ₹1,000 roll over to the next quarter.
          </p>
        </Card>
      )}

      <h2 className="mb-3 mt-8 text-lg font-semibold text-stone-900">Your tickets</h2>
      <div className="mb-4 flex flex-wrap gap-3">
        {STATUSES.map((s) => (
          <div key={s} className="flex items-center gap-2 rounded-md border border-stone-200 bg-white px-3 py-1.5 text-sm">
            <StatusBadge status={s} />
            <span className="font-semibold text-stone-900">{d.tickets_by_status[s] ?? 0}</span>
          </div>
        ))}
      </div>

      {recent.error && !recent.data ? (
        <ErrorState message={recent.error.message} onRetry={recent.reload} />
      ) : !recent.data ? (
        <PageSpinner />
      ) : recent.data.items.length === 0 ? (
        <EmptyState
          title="No support queries yet"
          description="Questions about royalties, ISBNs, printing, availability or production go here."
          action={<LinkButton to="/author/tickets/new">Submit your first query</LinkButton>}
        />
      ) : (
        <Card className="divide-y divide-stone-100 overflow-hidden">
          {recent.data.items.map((t) => (
            <TicketListRow key={t.ticket_number} ticket={t} />
          ))}
        </Card>
      )}
    </>
  )
}