import type { AuditEvent } from '../../lib/types'

export function describeAudit(e: AuditEvent): string {
  const who = e.actor?.name ?? 'System'
  switch (e.action) {
    case 'status_changed':
      return `${who} changed the status from ${e.old_value} to ${e.new_value}`
    case 'category_overridden':
      return `${who} set the category to ${e.new_value} (was ${e.old_value})`
    case 'priority_overridden':
      return `${who} set the priority to ${e.new_value} (was ${e.old_value})`
    case 'assigned':
      return e.new_value ? `${who} assigned the ticket to ${e.new_value}` : `${who} removed the assignee`
    case 'reply_sent':
      return `${who} sent a reply to the author`
    case 'note_added':
      return `${who} added an internal note`
    case 'ai_triaged':
      return `AI suggested ${e.new_value}`
    default:
      return `${who}: ${e.action}`
  }
}