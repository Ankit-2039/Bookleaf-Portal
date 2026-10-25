import { formatDateTime } from '../../../lib/format'
import type { AdminTicketDetail } from '../../../lib/types'

type Tone = 'author' | 'support' | 'internal'

const BUBBLE: Record<Tone, string> = {
  author: 'bg-white ring-1 ring-stone-200',
  support: 'bg-indigo-50 ring-1 ring-indigo-200',
  internal: 'bg-amber-50 border border-dashed border-amber-400',
}

function Bubble({ tone, who, at, body, tags = [] }: { tone: Tone; who: string; at: string; body: string; tags?: string[] }) {
  return (
    <div className={`flex ${tone === 'author' ? 'justify-start' : 'justify-end'}`}>
      <div className={`max-w-[90%] rounded-lg px-4 py-3 text-sm shadow-sm ${BUBBLE[tone]}`}>
        {tone === 'internal' && (
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-800">
            Internal note · not visible to the author
          </p>
        )}
        <p className="mb-1 flex flex-wrap items-center gap-x-2 text-xs font-medium text-stone-500">
          <span>{who} · {formatDateTime(at)}</span>
          {tags.map((t) => (
            <span key={t} className="rounded-full bg-white/70 px-2 py-0.5 text-[11px] text-stone-600 ring-1 ring-inset ring-stone-200">{t}</span>
          ))}
        </p>
        <p className="whitespace-pre-wrap break-words text-stone-900">{body}</p>
      </div>
    </div>
  )
}

export function ConversationPanel({ ticket }: { ticket: AdminTicketDetail }) {
  return (
    <div className="space-y-3" role="log" aria-live="polite" aria-label="Conversation">
      <Bubble tone="author" who={ticket.author.name} at={ticket.created_at} body={ticket.description} />
      {ticket.messages.map((m) => (
        <Bubble
          key={m.id}
          tone={m.kind === 'internal' ? 'internal' : 'support'}
          who={m.sender.name}
          at={m.created_at}
          body={m.body}
          tags={m.kind === 'public' && m.ai_drafted ? ['started from an AI draft'] : []}
        />
      ))}
    </div>
  )
}