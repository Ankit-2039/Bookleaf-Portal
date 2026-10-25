import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Card, EmptyState, ErrorState, PageHeader, PageSpinner, PriorityBadge, StatCard } from '../../components/ui'
import { useTheme } from '../../components/theme'
import { api } from '../../lib/api'
import { formatHours } from '../../lib/format'
import type { AdminTicketListItem } from '../../lib/types'
import { useNow } from '../../lib/useNow'
import { useResource } from '../../lib/useResource'
import { useLiveRefetch } from '../../realtime/hooks'
import { AgeBadge } from './shared'

function queueLink(filters: Record<string, string[]>): string {
  const p = new URLSearchParams()
  for (const [key, values] of Object.entries(filters)) values.forEach((v) => p.append(key, v))
  return `/admin/tickets?${p.toString()}`
}

const ACTIVE = ['Open', 'In Progress']

function StatLink({ to, label, value, hint }: { to: string; label: string; value: ReactNode; hint?: string }) {
  return (
    <Link
      to={to}
      className="block rounded-lg transition hover:ring-2 hover:ring-indigo-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
    >
      <StatCard label={label} value={value} hint={hint} />
    </Link>
  )
}

function MiniList({
  title, subtitle, tickets, now, emptyText,
}: { title: string; subtitle: string; tickets: AdminTicketListItem[]; now: number; emptyText: string }) {
  const theme = useTheme()
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-stone-100 px-4 py-3">
        <h2 className="font-semibold text-stone-900">{title}</h2>
        <p className="text-xs text-stone-500">{subtitle}</p>
      </div>
      {tickets.length === 0 ? (
        <p className="px-4 py-6 text-sm text-stone-500">{emptyText}</p>
      ) : (
        <ul className="divide-y divide-stone-100">
          {tickets.map((t) => (
            <li key={t.ticket_number}>
              <Link to={`/admin/tickets/${t.ticket_number}`} className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-stone-50">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-stone-900">
                    <span className={theme.link}>{t.display_id}</span> · {t.subject}
                  </p>
                  <p className="truncate text-xs text-stone-500">{t.author.name} · {t.category}</p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <PriorityBadge priority={t.priority} />
                  <span className="w-16 text-right"><AgeBadge ticket={t} now={now} /></span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

export function AdminDashboardPage() {
  const { data, error, reload } = useResource('admin-metrics', (s) => api.admin.metrics(s))
  useLiveRefetch(reload)
  const now = useNow()
  const theme = useTheme()

  if (error && !data) return <ErrorState message={error.message} onRetry={reload} />
  if (!data) return <PageSpinner />

  const m = data
  return (
    <>
      <PageHeader title="Operations overview" subtitle="A live view of the support queue. Cards open the matching queue." />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatLink to="/admin/tickets" label="Total tickets" value={m.total_tickets} />
        <StatLink to={queueLink({ status: ['Open'] })} label="Open" value={m.open_tickets} />
        <StatLink to={queueLink({ status: ['In Progress'] })} label="In progress" value={m.in_progress_tickets} />
        <StatLink to={queueLink({ status: ['Resolved'] })} label="Resolved" value={m.resolved_tickets} />
        <StatLink
          to={queueLink({ priority: ['Critical', 'High'], status: ACTIVE })}
          label="Urgent unresolved"
          value={<span className={m.urgent_unresolved > 0 ? 'text-red-700' : undefined}>{m.urgent_unresolved}</span>}
          hint="Critical + High, still open"
        />
        <StatLink
          to={queueLink({ assignee: ['unassigned'], status: ACTIVE })}
          label="Unassigned"
          value={<span className={m.unassigned_unresolved > 0 ? 'text-amber-700' : undefined}>{m.unassigned_unresolved}</span>}
          hint="Open or in progress, no owner"
        />
        <StatLink to={queueLink({ assignee: ['me'], status: ACTIVE })} label="Assigned to me" value={m.assigned_to_me} />
        <StatCard
          label="Avg. resolution time"
          value={formatHours(m.avg_resolution_hours)}
          hint={m.avg_resolution_hours == null ? 'No resolved tickets yet' : 'Opened → resolved'}
        />
      </div>

      {m.total_tickets === 0 ? (
        <div className="mt-8">
          <EmptyState title="No tickets yet" description="When an author submits a query, it appears here and in the queue within a second." />
        </div>
      ) : (
        <>
          <div className="mt-8 grid gap-6 xl:grid-cols-2">
            <MiniList
              title="Needs attention first"
              subtitle="Highest priority, then oldest. Unresolved only."
              tickets={m.urgent_queue}
              now={now}
              emptyText="No unresolved tickets. Everything is handled."
            />
            <MiniList
              title="Waiting the longest"
              subtitle="Oldest unresolved tickets, whatever their priority."
              tickets={m.longest_waiting}
              now={now}
              emptyText="No unresolved tickets."
            />
          </div>
          <div className="mt-4 text-right">
            <Link to="/admin/tickets" className={`text-sm font-medium ${theme.link}`}>Open the full queue →</Link>
          </div>
        </>
      )}
    </>
  )
}