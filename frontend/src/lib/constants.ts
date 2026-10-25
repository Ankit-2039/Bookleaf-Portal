import type { TicketCategory, TicketPriority, TicketStatus } from './types'

export const STATUSES: TicketStatus[] = ['Open', 'In Progress', 'Resolved', 'Closed']
export const PRIORITIES: TicketPriority[] = ['Critical', 'High', 'Medium', 'Low']
export const CATEGORIES: TicketCategory[] = [
  'Royalty & Payments',
  'ISBN & Metadata Issues',
  'Printing & Quality',
  'Distribution & Availability',
  'Book Status & Production Updates',
  'General Inquiry',
]

// Mirrors the backend rules so the UI only offers moves the API will accept.
export const ALLOWED_TRANSITIONS: Record<TicketStatus, TicketStatus[]> = {
  Open: ['In Progress', 'Resolved', 'Closed'],
  'In Progress': ['Open', 'Resolved', 'Closed'],
  Resolved: ['In Progress', 'Closed'],
  Closed: [],
}

// An unresolved ticket's age turns amber, then red, past these thresholds.
export const AGE_WARN_HOURS = 48
export const AGE_ALERT_HOURS = 168 // 7 days