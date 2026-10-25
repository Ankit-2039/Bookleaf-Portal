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