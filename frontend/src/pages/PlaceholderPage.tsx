import { useEffect, useState } from 'react'
import { useAuth } from '../auth/useAuth'
import { Card, PageHeader } from '../components/ui'
import type { RealtimeEvent } from '../realtime/context'
import { useRealtime } from '../realtime/hooks'

function LiveEventLog() {
  const { status, subscribe } = useRealtime()
  const [events, setEvents] = useState<RealtimeEvent[]>([])

  useEffect(() => subscribe((e) => setEvents((prev) => [e, ...prev].slice(0, 8))), [subscribe])

  return (
    <div>
      <p className="text-sm font-medium text-stone-700">Realtime connection: {status}</p>
      {events.length === 0 ? (
        <p className="mt-1 text-sm text-stone-500">No events yet. Reply to a ticket as an admin to see one arrive here.</p>
      ) : (
        <ul className="mt-2 space-y-1 font-mono text-xs text-stone-600">
          {events.map((e, i) => (
            <li key={i}>{JSON.stringify(e)}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Temporary screen: Steps 10 and 11 replace it with the real pages. */
export function PlaceholderPage({ title }: { title: string }) {
  const { user } = useAuth()
  return (
    <>
      <PageHeader title={title} subtitle="This screen is built in the next step." />
      <Card className="space-y-4 p-5">
        <p className="text-sm text-stone-700">
          Signed in as <strong>{user?.name}</strong> ({user?.email}), role <code>{user?.role}</code>.
        </p>
        <LiveEventLog />
      </Card>
    </>
  )
}