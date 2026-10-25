import { createContext } from 'react'

export type RealtimeStatus = 'connecting' | 'connected' | 'disconnected'

export interface TicketEvent {
  type: 'ticket.created' | 'ticket.updated'
  ticket_number: number
  reason: string
  at: string
}
/** 'resync' is raised locally after a reconnect: events missed while offline are not replayed. */
export type RealtimeEvent = TicketEvent | { type: 'resync' }
export type Listener = (event: RealtimeEvent) => void

export interface RealtimeContextValue {
  status: RealtimeStatus
  subscribe: (fn: Listener) => () => void
}

export const RealtimeContext = createContext<RealtimeContextValue | null>(null)