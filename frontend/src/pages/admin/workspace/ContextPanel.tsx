import type { ReactNode } from 'react'
import { Card } from '../../../components/ui'
import { formatDate, formatINR } from '../../../lib/format'
import type { AdminTicketDetail } from '../../../lib/types'

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex justify-between gap-3 py-1 text-sm">
      <dt className="text-stone-500">{label}</dt>
      <dd className="text-right font-medium text-stone-900">{children}</dd>
    </div>
  )
}

export function ContextPanel({ ticket }: { ticket: AdminTicketDetail }) {
  const a = ticket.author
  const b = ticket.book_detail
  return (
    <Card className="p-4">
      <h2 className="mb-2 font-semibold text-stone-900">Author &amp; book</h2>
      <dl className="divide-y divide-stone-100">
        <Row label="Author">{a.name}</Row>
        <Row label="Email"><a className="break-all text-indigo-600 hover:underline" href={`mailto:${a.email}`}>{a.email}</a></Row>
        <Row label="Author ID">{a.author_code}</Row>
        {a.city && <Row label="City">{a.city}</Row>}
      </dl>

      <h3 className="mb-1 mt-4 text-sm font-semibold text-stone-900">{b ? b.title : 'General / Account Level'}</h3>
      {b ? (
        <>
          <dl className="divide-y divide-stone-100">
            <Row label="Status">{b.status}</Row>
            <Row label="ISBN on record">{b.isbn ?? '—'}</Row>
            <Row label="Published">{b.publication_date ? formatDate(b.publication_date) : 'Not yet'}</Row>
            <Row label="MRP">{formatINR(b.mrp)}</Row>
            <Row label="Copies sold">{b.total_copies_sold.toLocaleString('en-IN')}</Row>
            <Row label="Royalty earned">{formatINR(b.total_royalty_earned)}</Row>
            <Row label="Royalty paid">{formatINR(b.royalty_paid)}</Row>
            <Row label="Royalty pending">{formatINR(b.royalty_pending)}</Row>
            <Row label="Last payout">{formatDate(b.last_royalty_payout_date)}</Row>
            <Row label="Print partner">{b.print_partner ?? '—'}</Row>
            <Row label="Listed on">{b.available_on.length ? b.available_on.join(', ') : 'Nowhere yet'}</Row>
          </dl>
          <p className="mt-2 text-xs text-stone-500">These stored figures are exactly what the AI sees when it drafts a reply.</p>
        </>
      ) : (
        <p className="text-sm text-stone-500">This query isn't tied to a specific book.</p>
      )}
    </Card>
  )
}