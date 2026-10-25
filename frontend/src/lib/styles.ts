import type { TicketPriority, TicketStatus } from './types'

export const STATUS_STYLES: Record<TicketStatus, string> = {
  Open: 'bg-blue-50 text-blue-700 ring-blue-200',
  'In Progress': 'bg-amber-50 text-amber-800 ring-amber-200',
  Resolved: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  Closed: 'bg-stone-100 text-stone-600 ring-stone-200',
}

export const PRIORITY_STYLES: Record<TicketPriority, string> = {
  Critical: 'bg-red-600 text-white ring-red-700',
  High: 'bg-orange-50 text-orange-700 ring-orange-200',
  Medium: 'bg-yellow-50 text-yellow-800 ring-yellow-200',
  Low: 'bg-stone-100 text-stone-600 ring-stone-200',
}