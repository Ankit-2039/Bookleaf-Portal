import { useContext, useEffect, useRef } from 'react'
import { RealtimeContext } from './context'

export function useRealtime() {
  const ctx = useContext(RealtimeContext)
  if (!ctx) throw new Error('useRealtime must be used inside <RealtimeProvider>')
  return ctx
}

/**
 * Keeps a page fresh. Events carry no data, so on a relevant event (or after a reconnect) we call
 * `refetch`, which reads canonical state through the REST API. While the socket is not connected
 * we poll instead. Pass `ticketNumber` to react only to events about that ticket.
 */
export function useLiveRefetch(refetch: () => void, options: { ticketNumber?: number; pollMs?: number } = {}) {
  const { ticketNumber, pollMs = 10_000 } = options
  const { status, subscribe } = useRealtime()
  const latest = useRef(refetch)
  useEffect(() => {
    latest.current = refetch
  })

  useEffect(
    () =>
      subscribe((event) => {
        if (event.type === 'resync' || ticketNumber === undefined || event.ticket_number === ticketNumber) {
          latest.current()
        }
      }),
    [subscribe, ticketNumber],
  )

  useEffect(() => {
    if (status === 'connected') return
    const id = window.setInterval(() => latest.current(), pollMs)
    return () => window.clearInterval(id)
  }, [status, pollMs])
}