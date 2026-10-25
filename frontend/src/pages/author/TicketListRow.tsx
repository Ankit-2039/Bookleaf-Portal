import { Link } from 'react-router-dom'
import { PriorityBadge, StatusBadge } from '../../components/ui'
import { formatDate, formatDateTime } from '../../lib/format'
import type { AuthorTicketListItem } from '../../lib/types'

export function TicketListRow({ ticket: t }: { ticket: AuthorTicketListItem }) {
  return (
    <Link
      to={`/author/tickets/${t.ticket_number}`}
      className="block px-4 py-3 hover:bg-stone-50 focus-visible:bg-stone-50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-emerald-600"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-medium text-stone-900">{t.subject}</p>
          <p className="mt-0.5 text-xs text-stone-500">
            {t.display_id} · {t.book?.title ?? 'General / Account Level'} · {t.category}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <PriorityBadge priority={t.priority} />
          <StatusBadge status={t.status} />
        </div>
      </div>
      <p className="mt-1 text-xs text-stone-400">
        Opened {formatDate(t.created_at)} · Updated {formatDateTime(t.updated_at)}
      </p>
    </Link>
  )
}