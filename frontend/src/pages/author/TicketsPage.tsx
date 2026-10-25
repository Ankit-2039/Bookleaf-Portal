import { useState } from 'react'
import { LinkButton } from '../../components/LinkButton'
import { Button, Card, EmptyState, ErrorState, PageHeader, PageSpinner, Select } from '../../components/ui'
import { api } from '../../lib/api'
import { STATUSES } from '../../lib/constants'
import type { TicketStatus } from '../../lib/types'
import { useResource } from '../../lib/useResource'
import { useLiveRefetch } from '../../realtime/hooks'
import { TicketListRow } from './TicketListRow'

const PAGE_SIZE = 10

export function TicketsPage() {
  const [status, setStatus] = useState<TicketStatus | ''>('')
  const [page, setPage] = useState(1)

  const key = `author-tickets|${status}|${page}`
  const { data, error, loading, reload } = useResource(key, (s) =>
    api.author.tickets({ status: status || undefined, page, page_size: PAGE_SIZE }, s),
  )
  useLiveRefetch(reload)

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <>
      <PageHeader
        title="My Tickets"
        subtitle="Replies from the BookLeaf team appear here automatically."
        actions={<LinkButton to="/author/tickets/new">Submit a query</LinkButton>}
      />

      <div className="mb-4 max-w-xs">
        <Select
          aria-label="Filter by status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value as TicketStatus | '')
            setPage(1)
          }}
        >
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </Select>
      </div>

      {error && !data ? (
        <ErrorState message={error.message} onRetry={reload} />
      ) : !data ? (
        <PageSpinner />
      ) : data.items.length === 0 ? (
        page > 1 ? (
          <EmptyState title="No tickets on this page" action={<Button variant="secondary" onClick={() => setPage(1)}>Back to first page</Button>} />
        ) : status ? (
          <EmptyState title={`No ${status} tickets`} description="Try a different status filter." />
        ) : (
          <EmptyState
            title="You haven't submitted any queries yet"
            description="Questions about royalties, ISBNs, printing, availability or production go here."
            action={<LinkButton to="/author/tickets/new">Submit your first query</LinkButton>}
          />
        )
      ) : (
        <>
          <Card className={`divide-y divide-stone-100 overflow-hidden ${loading ? 'opacity-60' : ''}`}>
            {data.items.map((t) => (
              <TicketListRow key={t.ticket_number} ticket={t} />
            ))}
          </Card>
          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between text-sm text-stone-600">
              <span>Page {page} of {totalPages} · {data.total} tickets</span>
              <div className="flex gap-2">
                <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</Button>
                <Button variant="secondary" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</Button>
              </div>
            </div>
          )}
        </>
      )}
    </>
  )
}