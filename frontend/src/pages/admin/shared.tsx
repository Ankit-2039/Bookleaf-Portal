import { AGE_ALERT_HOURS, AGE_WARN_HOURS } from '../../lib/constants'
import { formatAge, formatDate, formatDateTime } from '../../lib/format'
import type { AdminTicketListItem } from '../../lib/types'

const isActive = (t: Pick<AdminTicketListItem, 'status'>) => t.status === 'Open' || t.status === 'In Progress'

/** How long an unresolved ticket has been waiting. Resolved/closed tickets show their opening date instead. */
export function AgeBadge({ ticket, now }: { ticket: Pick<AdminTicketListItem, 'status' | 'created_at'>; now: number }) {
  if (!isActive(ticket)) {
    return <span className="text-xs text-stone-400">{formatDate(ticket.created_at)}</span>
  }
  const hours = (now - new Date(ticket.created_at).getTime()) / 3_600_000
  const tone =
    hours >= AGE_ALERT_HOURS ? 'font-semibold text-red-700' : hours >= AGE_WARN_HOURS ? 'font-medium text-amber-700' : 'text-stone-600'
  return (
    <span className={`text-sm ${tone}`} title={`Opened ${formatDateTime(ticket.created_at)}`}>
      {formatAge(ticket.created_at, now)}
    </span>
  )
}

/** Small honest notes about how a ticket was classified. */
export function AiFlag({ ticket }: { ticket: Pick<AdminTicketListItem, 'classification_status' | 'category_overridden'> }) {
  if (ticket.category_overridden) return <span className="text-xs text-indigo-600">edited by admin</span>
  if (ticket.classification_status === 'pending') return <span className="text-xs text-stone-400">AI pending…</span>
  if (ticket.classification_status === 'failed') {
    return <span className="text-xs font-medium text-amber-700">AI failed: set manually</span>
  }
  return null
}
