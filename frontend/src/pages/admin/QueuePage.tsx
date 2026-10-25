import { useSearchParams, Link } from 'react-router-dom'
import { useTheme } from '../../components/theme'
import {
  Button, Card, EmptyState, ErrorState, Input, PageHeader, PageSpinner, PriorityBadge, Select, StatusBadge,
} from '../../components/ui'
import { api } from '../../lib/api'
import { CATEGORIES, PRIORITIES, STATUSES } from '../../lib/constants'
import { formatAge } from '../../lib/format'
import type { AdminQueueQuery } from '../../lib/types'
import { useDebounced } from '../../lib/useDebounced'
import { useNow } from '../../lib/useNow'
import { useResource } from '../../lib/useResource'
import { useLiveRefetch } from '../../realtime/hooks'
import { AgeBadge, AiFlag } from './shared'
import { rowAccent } from './rowAccent'

const PAGE_SIZE = 20
type SortKey = NonNullable<AdminQueueQuery['sort']>
const SORTS: { value: SortKey; label: string }[] = [
  { value: 'urgency', label: 'Most urgent first' },
  { value: 'oldest', label: 'Oldest first' },
  { value: 'newest', label: 'Newest first' },
  { value: 'updated', label: 'Recently updated' },
]
const OBJECT_ID = /^[0-9a-f]{24}$/
const DATE = /^\d{4}-\d{2}-\d{2}$/

/** Keep only values from the allowed list: a hand-edited URL can't send garbage to the API. */
function pickList<T extends string>(values: string[], allowed: readonly T[]): T[] {
  return allowed.filter((a) => values.includes(a))
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset transition ${
        active ? 'bg-indigo-600 text-white ring-indigo-600' : 'bg-white text-stone-700 ring-stone-300 hover:bg-stone-50'
      }`}
    >
      {children}
    </button>
  )
}

export function QueuePage() {
  const theme = useTheme()
  const now = useNow()
  const [params, setParams] = useSearchParams()

  // ---- filters, read from the URL and validated ----
  const statuses = pickList(params.getAll('status'), STATUSES)
  const priorities = pickList(params.getAll('priority'), PRIORITIES)
  const category = CATEGORIES.find((c) => c === params.get('category'))
  const assigneeRaw = params.get('assignee') ?? ''
  const assignee = assigneeRaw === 'me' || assigneeRaw === 'unassigned' || OBJECT_ID.test(assigneeRaw) ? assigneeRaw : ''
  const dateFromRaw = params.get('date_from') ?? ''
  const dateToRaw = params.get('date_to') ?? ''
  const dateFrom = DATE.test(dateFromRaw) ? dateFromRaw : ''
  const dateTo = DATE.test(dateToRaw) ? dateToRaw : ''
  const qRaw = params.get('q') ?? ''
  const sort = SORTS.find((s) => s.value === params.get('sort'))?.value ?? 'urgency'
  const page = Math.max(1, parseInt(params.get('page') ?? '1', 10) || 1)
  const q = useDebounced(qRaw.trim(), 300)

  function update(patch: Record<string, string | string[] | null>, keepPage = false) {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        for (const [key, value] of Object.entries(patch)) {
          next.delete(key)
          if (Array.isArray(value)) value.forEach((v) => next.append(key, v))
          else if (value) next.set(key, value)
        }
        if (!keepPage) next.delete('page')
        return next
      },
      { replace: true },
    )
  }

  function toggle<T extends string>(key: string, current: T[], value: T) {
    update({ [key]: current.includes(value) ? current.filter((v) => v !== value) : [...current, value] })
  }

  const query: AdminQueueQuery = {
    status: statuses.length ? statuses : undefined,
    priority: priorities.length ? priorities : undefined,
    category: category ? [category] : undefined,
    assignee: assignee || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    q: q || undefined,
    sort,
    page,
    page_size: PAGE_SIZE,
  }
  const { data, error, loading, reload } = useResource(`admin-queue|${JSON.stringify(query)}`, (s) =>
    api.admin.tickets(query, s),
  )
  const admins = useResource('admin-admins', (s) => api.admin.admins(s))
  useLiveRefetch(reload) // a new ticket or a finished AI triage refreshes the queue

  const hasFilters = !!(statuses.length || priorities.length || category || assignee || dateFrom || dateTo || qRaw)
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <>
      <PageHeader title="Ticket Queue" subtitle="Unresolved tickets are sorted by priority, then age. The oldest critical ones come first." />

      <Card className="mb-5 space-y-4 p-4">
        <Input
          type="search"
          aria-label="Search tickets"
          placeholder="Search by ticket number, subject, author name or email"
          value={qRaw}
          onChange={(e) => update({ q: e.target.value || null })}
          maxLength={100}
        />

        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter by status">
          <span className="w-16 text-xs font-medium text-stone-500">Status</span>
          {STATUSES.map((s) => (
            <Chip key={s} active={statuses.includes(s)} onClick={() => toggle('status', statuses, s)}>{s}</Chip>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter by priority">
          <span className="w-16 text-xs font-medium text-stone-500">Priority</span>
          {PRIORITIES.map((p) => (
            <Chip key={p} active={priorities.includes(p)} onClick={() => toggle('priority', priorities, p)}>{p}</Chip>
          ))}
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Select aria-label="Filter by category" value={category ?? ''} onChange={(e) => update({ category: e.target.value || null })}>
            <option value="">All categories</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </Select>
          <Select aria-label="Filter by assignee" value={assignee} onChange={(e) => update({ assignee: e.target.value || null })}>
            <option value="">Anyone</option>
            <option value="me">Assigned to me</option>
            <option value="unassigned">Unassigned</option>
            {admins.data?.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </Select>
          <Input type="date" aria-label="Created from" value={dateFrom} max={dateTo || undefined} onChange={(e) => update({ date_from: e.target.value || null })} />
          <Input type="date" aria-label="Created to" value={dateTo} min={dateFrom || undefined} onChange={(e) => update({ date_to: e.target.value || null })} />
          <Select aria-label="Sort order" value={sort} onChange={(e) => update({ sort: e.target.value === 'urgency' ? null : e.target.value })}>
            {SORTS.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </Select>
        </div>

        {hasFilters && (
          <div>
            <Button variant="ghost" onClick={() => setParams({}, { replace: true })}>Clear all filters</Button>
          </div>
        )}
      </Card>

      {error && !data ? (
        <ErrorState message={error.message} onRetry={reload} />
      ) : !data ? (
        <PageSpinner />
      ) : data.items.length === 0 ? (
        page > 1 ? (
          <EmptyState title="No tickets on this page" action={<Button variant="secondary" onClick={() => update({ page: null })}>Back to first page</Button>} />
        ) : hasFilters ? (
          <EmptyState title="No tickets match these filters" description="Widen or clear the filters to see more." action={<Button variant="secondary" onClick={() => setParams({}, { replace: true })}>Clear all filters</Button>} />
        ) : (
          <EmptyState title="The queue is empty" description="New author queries will appear here as soon as they are submitted." />
        )
      ) : (
        <>
          <p className="mb-2 text-sm text-stone-500" aria-live="polite">
            Showing {(data.page - 1) * data.page_size + 1}–{(data.page - 1) * data.page_size + data.items.length} of {data.total} tickets
          </p>
          <Card className={`overflow-hidden ${loading ? 'opacity-60' : ''}`}>
            <div className="overflow-x-auto" aria-busy={loading}>
              <table className="min-w-full divide-y divide-stone-200 text-left text-sm">
                <thead className="bg-stone-50 text-xs uppercase tracking-wide text-stone-500">
                  <tr>
                    {['Ticket', 'Subject', 'Author', 'Category', 'Priority', 'Status', 'Assignee', 'Age', 'Updated'].map((h) => (
                      <th key={h} scope="col" className="px-4 py-3 font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 bg-white">
                  {data.items.map((t) => (
                    <tr key={t.ticket_number} className="hover:bg-stone-50">
                      <td className={`whitespace-nowrap border-l-4 px-4 py-3 font-medium ${rowAccent(t)}`}>
                        <Link to={`/admin/tickets/${t.ticket_number}`} className={theme.link}>{t.display_id}</Link>
                      </td>
                      <td className="max-w-xs px-4 py-3">
                        <Link to={`/admin/tickets/${t.ticket_number}`} className="block truncate font-medium text-stone-900 hover:underline">{t.subject}</Link>
                        <p className="truncate text-xs text-stone-500">{t.book?.title ?? 'General / Account Level'}</p>
                      </td>
                      <td className="px-4 py-3">
                        <p className="whitespace-nowrap text-stone-900">{t.author.name}</p>
                        <p className="text-xs text-stone-500">{t.author.email}</p>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-stone-800">{t.category}</p>
                        <AiFlag ticket={t} />
                      </td>
                      <td className="whitespace-nowrap px-4 py-3">
                        <PriorityBadge priority={t.priority} />
                        {t.priority_overridden && <p className="text-xs text-indigo-600">edited by admin</p>}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3"><StatusBadge status={t.status} /></td>
                      <td className="whitespace-nowrap px-4 py-3">
                        {t.assignee ? t.assignee.name : <span className="text-stone-400">Unassigned</span>}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3"><AgeBadge ticket={t} now={now} /></td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-stone-500">{formatAge(t.updated_at, now)} ago</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between text-sm text-stone-600">
              <span>Page {page} of {totalPages}</span>
              <div className="flex gap-2">
                <Button variant="secondary" disabled={page <= 1} onClick={() => update({ page: String(page - 1) }, true)}>Previous</Button>
                <Button variant="secondary" disabled={page >= totalPages} onClick={() => update({ page: String(page + 1) }, true)}>Next</Button>
              </div>
            </div>
          )}
        </>
      )}
    </>
  )
}