import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useAuth } from '../auth/useAuth'
import { RealtimeContext, type Listener, type RealtimeContextValue, type RealtimeEvent, type RealtimeStatus } from './context'

const PING_MS = 30_000
const MAX_BACKOFF_MS = 30_000

function wsUrl(): string {
  const base = import.meta.env.VITE_API_URL as string | undefined
  if (base) return `${base.replace(/\/$/, '').replace(/^http/, 'ws')}/api/v1/ws`
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/api/v1/ws`
}

export function RealtimeProvider({ children }: { children: ReactNode }) {
  const { token, logout } = useAuth()
  const [status, setStatus] = useState<RealtimeStatus>('connecting')
  const listeners = useRef(new Set<Listener>())

  const subscribe = useCallback((fn: Listener) => {
    listeners.current.add(fn)
    return () => {
      listeners.current.delete(fn)
    }
  }, [])

  useEffect(() => {
    if (!token) return
    let socket = null as WebSocket | null
    let retryTimer: number | undefined
    let pingTimer: number | undefined
    let attempt = 0
    let stopped = false
    let needsResync = false

    const emit = (event: RealtimeEvent) => {
      listeners.current.forEach((fn) => {
        try {
          fn(event)
        } catch {
          /* one broken listener must not affect the others */
        }
      })
    }

    const connect = () => {
      const ws = new WebSocket(wsUrl())
      socket = ws

      // Auth is the first message (not the URL), so tokens never end up in server or proxy logs.
      ws.onopen = () => ws.send(JSON.stringify({ type: 'auth', token }))

      ws.onmessage = (e) => {
        let msg: unknown
        try {
          msg = JSON.parse(String(e.data))
        } catch {
          return
        }
        if (!msg || typeof msg !== 'object') return
        const m = msg as { type?: string; ticket_number?: unknown; reason?: unknown; at?: unknown }

        if (m.type === 'ready') {
          attempt = 0
          setStatus('connected')
          window.clearInterval(pingTimer)
          pingTimer = window.setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) ws.send('{"type":"ping"}')
          }, PING_MS)
          if (needsResync) {
            needsResync = false
            emit({ type: 'resync' }) // we may have missed events while offline: refetch everything
          }
        } else if ((m.type === 'ticket.created' || m.type === 'ticket.updated') && typeof m.ticket_number === 'number') {
          emit({ type: m.type, ticket_number: m.ticket_number, reason: String(m.reason ?? ''), at: String(m.at ?? '') })
        }
      }

      ws.onclose = (e) => {
        window.clearInterval(pingTimer)
        if (stopped || socket !== ws) return
        needsResync = true
        setStatus('disconnected')
        if (e.code === 4401) {
          logout() // token rejected or expired: the session is over
          return
        }
        if (e.code === 4403) return // origin refused: retrying won't help, polling keeps the page fresh
        const delay = Math.min(1000 * 2 ** attempt, MAX_BACKOFF_MS)
        attempt += 1
        retryTimer = window.setTimeout(() => {
          setStatus('connecting')
          connect()
        }, delay)
      }

      ws.onerror = () => ws.close()
    }

    connect()
    return () => {
      stopped = true
      window.clearTimeout(retryTimer)
      window.clearInterval(pingTimer)
      socket?.close()
    }
  }, [token, logout])

  const value = useMemo<RealtimeContextValue>(() => ({ status, subscribe }), [status, subscribe])
  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>
}