import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, EmptyState, ErrorState, Input, PageHeader, PageSpinner, Select } from '../../components/ui'
import { api } from '../../lib/api'
import { formatDate, formatINR } from '../../lib/format'
import type { Book } from '../../lib/types'
import { useDebounced } from '../../lib/useDebounced'
import { useResource } from '../../lib/useResource'

type Filter = 'all' | 'live' | 'production'
type Sort = 'title' | 'publication_date' | 'royalty_pending'

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-stone-500">{label}</dt>
      <dd className="text-sm font-medium text-stone-900">{children}</dd>
    </div>
  )
}

function BookCard({ book: b }: { book: Book }) {
  const showRoyalties = b.is_published || b.total_royalty_earned > 0
  const neverPaid = b.is_published && b.total_royalty_earned > 0 && b.royalty_paid === 0 && !b.last_royalty_payout_date

  return (
    <Card className="flex flex-col p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h2 className="text-lg font-semibold text-stone-900">{b.title}</h2>
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${
            b.is_published ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : 'bg-amber-50 text-amber-800 ring-amber-200'
          }`}
        >
          {b.status}
        </span>
      </div>
      <p className="mt-0.5 text-sm text-stone-500">{b.genre ?? 'Genre not set'}</p>

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
        <Detail label="ISBN">{b.isbn ?? '—'}</Detail>
        <Detail label="Published">{b.publication_date ? formatDate(b.publication_date) : 'Not yet published'}</Detail>
        <Detail label="MRP">{formatINR(b.mrp)}</Detail>
        <Detail label="Copies sold">{b.total_copies_sold.toLocaleString('en-IN')}</Detail>
      </dl>

      <div className="mt-4 rounded-md bg-stone-50 p-3">
        {showRoyalties ? (
          <>
            <dl className="grid grid-cols-3 gap-3">
              <Detail label="Royalty earned">{formatINR(b.total_royalty_earned)}</Detail>
              <Detail label="Paid">{formatINR(b.royalty_paid)}</Detail>
              <Detail label="Pending">
                <span className={b.royalty_pending > 0 ? 'text-amber-700' : undefined}>{formatINR(b.royalty_pending)}</span>
              </Detail>
            </dl>
            {neverPaid && <p className="mt-2 text-xs text-amber-800">No payout recorded yet for this book.</p>}
            {b.last_royalty_payout_date && (
              <p className="mt-2 text-xs text-stone-500">Last payout: {formatDate(b.last_royalty_payout_date)}</p>
            )}
          </>
        ) : (
          <p className="text-sm text-stone-600">Royalties start accruing once the book is published.</p>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-stone-500">
        <span>Printed by: {b.print_partner ?? 'not assigned yet'}</span>
        {b.available_on.length > 0 ? (
          <span className="flex flex-wrap gap-1">
            {b.available_on.map((p) => (
              <span key={p} className="rounded-full bg-stone-100 px-2 py-0.5 ring-1 ring-inset ring-stone-200">{p}</span>
            ))}
          </span>
        ) : (
          <span>Not listed on any platform yet</span>
        )}
      </div>

      <div className="mt-4 border-t border-stone-100 pt-3">
        <Link to={`/author/tickets/new?book=${b.id}`} className="text-sm font-medium text-emerald-700 hover:text-emerald-900">
          Raise a query about this book →
        </Link>
      </div>
    </Card>
  )
}

export function BooksPage() {
  const [q, setQ] = useState('')
  const [filter, setFilter] = useState<Filter>('all')
  const [sort, setSort] = useState<Sort>('title')
  const [order, setOrder] = useState<'asc' | 'desc'>('asc')

  const search = useDebounced(q.trim(), 300)
  const published = filter === 'all' ? undefined : filter === 'live'
  const key = `author-books|${search}|${filter}|${sort}|${order}`
  const { data, error, loading, reload } = useResource(key, (s) =>
    api.author.books({ q: search || undefined, published, sort, order }, s),
  )

  const filtering = search !== '' || filter !== 'all'

  return (
    <>
      <PageHeader title="My Books" subtitle="Your catalog with sales and royalty figures." />

      <div className="mb-5 grid gap-3 sm:grid-cols-[1fr_auto_auto_auto]">
        <Input
          type="search"
          aria-label="Search books"
          placeholder="Search by title, ISBN or genre"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          maxLength={100}
        />
        <Select aria-label="Filter by status" value={filter} onChange={(e) => setFilter(e.target.value as Filter)}>
          <option value="all">All books</option>
          <option value="live">Published &amp; live</option>
          <option value="production">In production</option>
        </Select>
        <Select aria-label="Sort by" value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
          <option value="title">Sort: Title</option>
          <option value="publication_date">Sort: Publication date</option>
          <option value="royalty_pending">Sort: Royalty pending</option>
        </Select>
        <Select aria-label="Sort order" value={order} onChange={(e) => setOrder(e.target.value as 'asc' | 'desc')}>
          <option value="asc">Ascending</option>
          <option value="desc">Descending</option>
        </Select>
      </div>

      {error && !data ? (
        <ErrorState message={error.message} onRetry={reload} />
      ) : !data ? (
        <PageSpinner />
      ) : data.length === 0 ? (
        filtering ? (
          <EmptyState title="No books match your search" description="Try a different search or clear the filter." />
        ) : (
          <EmptyState title="No books on your account yet" description="Once your first book is added, it will appear here." />
        )
      ) : (
        <div className={`grid gap-4 lg:grid-cols-2 ${loading ? 'opacity-60' : ''}`} aria-busy={loading}>
          {data.map((b) => (
            <BookCard key={b.id} book={b} />
          ))}
        </div>
      )}
    </>
  )
}