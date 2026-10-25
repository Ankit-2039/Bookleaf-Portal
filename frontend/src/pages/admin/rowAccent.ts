import type { AdminTicketListItem } from '../../lib/types'

/** Left-edge colour that makes unresolved Critical/High tickets stand out in a long table. */
export function rowAccent(t: Pick<AdminTicketListItem, 'status' | 'priority'>): string {
  const active = t.status === 'Open' || t.status === 'In Progress'
  if (!active) return 'border-l-transparent'
  if (t.priority === 'Critical') return 'border-l-red-600'
  if (t.priority === 'High') return 'border-l-orange-400'
  return 'border-l-transparent'
}