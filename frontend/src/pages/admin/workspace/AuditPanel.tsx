import { Card } from '../../../components/ui'
import { formatDateTime } from '../../../lib/format'
import type { AdminTicketDetail } from '../../../lib/types'
import { describeAudit } from '../auditLabels'

export function AuditPanel({ ticket }: { ticket: AdminTicketDetail }) {
  const events = [...ticket.audit].reverse() // newest first
  return (
    <Card className="p-4">
      <details>
        <summary className="cursor-pointer font-semibold text-stone-900">History ({events.length})</summary>
        {events.length === 0 ? (
          <p className="mt-2 text-sm text-stone-500">No actions recorded yet.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {events.map((e) => (
              <li key={e.id} className="text-sm text-stone-700">
                {describeAudit(e)}
                <span className="block text-xs text-stone-400">{formatDateTime(e.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </details>
    </Card>
  )
}