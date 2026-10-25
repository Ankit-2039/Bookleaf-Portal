import { useState } from 'react'
import { Alert, Button, Card, Textarea } from '../../../components/ui'
import { api, toApiError, type ApiError } from '../../../lib/api'
import { newId } from '../../../lib/ids'
import type { AdminTicketDetail } from '../../../lib/types'

interface Props { ticket: AdminTicketDetail; onChanged: () => void; onError: (e: ApiError) => void }
interface DraftInfo { verify: string[]; warnings: string[]; model: string }
type Mode = 'reply' | 'note'

function ModeButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`rounded-md px-3 py-1.5 text-sm font-medium ring-1 ring-inset transition ${
        active ? 'bg-indigo-600 text-white ring-indigo-600' : 'bg-white text-stone-700 ring-stone-300 hover:bg-stone-50'
      }`}
    >
      {children}
    </button>
  )
}

export function Composer({ ticket, onChanged, onError }: Props) {
  const n = ticket.ticket_number
  const [mode, setMode] = useState<Mode>('reply')

  // reply state
  const [replyText, setReplyText] = useState('')
  const [fromDraft, setFromDraft] = useState(false)
  const [draftInfo, setDraftInfo] = useState<DraftInfo | null>(null)
  const [drafting, setDrafting] = useState(false)
  const [draftError, setDraftError] = useState<string | null>(null)
  const [confirmReplace, setConfirmReplace] = useState(false)
  const [resolveAfter, setResolveAfter] = useState(false)
  const [sending, setSending] = useState(false)
  // Stable until a send succeeds, so a retried request can never create a duplicate message.
  const [clientMsgId, setClientMsgId] = useState(() => newId())

  // note state
  const [noteText, setNoteText] = useState('')
  const [savingNote, setSavingNote] = useState(false)

  const closed = ticket.status === 'Closed'
  const canResolve = ticket.status === 'Open' || ticket.status === 'In Progress'

  async function generate() {
    setConfirmReplace(false)
    setDrafting(true)
    setDraftError(null)
    try {
      const d = await api.admin.draft(n)
      setReplyText(d.draft)
      setFromDraft(true)
      setDraftInfo({ verify: d.verify_before_sending, warnings: d.warnings, model: d.model })
    } catch (e) {
      const err = toApiError(e)
      setDraftError(err.retryAfter ? `${err.message} (try again in about ${err.retryAfter} s)` : err.message)
    } finally {
      setDrafting(false)
    }
  }

  function onDraftClick() {
    if (replyText.trim() && !confirmReplace) {
      setConfirmReplace(true) // don't silently overwrite what the admin has written
      return
    }
    void generate()
  }

  function onReplyChange(value: string) {
    setReplyText(value)
    if (value.trim() === '') {
      setFromDraft(false)
      setDraftInfo(null)
    }
  }

  async function sendReply() {
    const body = replyText.trim()
    if (!body || sending) return
    setSending(true)
    try {
      await api.admin.reply(n, {
        body,
        client_msg_id: clientMsgId,
        from_ai_draft: fromDraft,
        set_status: resolveAfter && canResolve ? 'Resolved' : undefined,
      })
      setReplyText('')
      setFromDraft(false)
      setDraftInfo(null)
      setDraftError(null)
      setResolveAfter(false)
      setClientMsgId(newId())
      onChanged()
    } catch (e) {
      onError(toApiError(e))
    } finally {
      setSending(false)
    }
  }

  async function saveNote() {
    const body = noteText.trim()
    if (!body || savingNote) return
    setSavingNote(true)
    try {
      await api.admin.addNote(n, body)
      setNoteText('')
      onChanged()
    } catch (e) {
      onError(toApiError(e))
    } finally {
      setSavingNote(false)
    }
  }

  return (
    <Card className="p-4">
      <div className="mb-4 flex gap-2" role="group" aria-label="Compose">
        <ModeButton active={mode === 'reply'} onClick={() => setMode('reply')}>Reply to author</ModeButton>
        <ModeButton active={mode === 'note'} onClick={() => setMode('note')}>Internal note</ModeButton>
      </div>

      {mode === 'reply' ? (
        closed ? (
          <Alert tone="info">This ticket is closed, so replies are turned off. You can still add internal notes.</Alert>
        ) : (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <label htmlFor="reply" className="text-sm font-medium text-stone-700">
                Your reply <span className="font-normal text-stone-500">· the author will see this</span>
              </label>
              <Button variant="secondary" loading={drafting} onClick={onDraftClick}>
                {draftInfo ? 'Regenerate AI draft' : 'Draft with AI'}
              </Button>
            </div>

            {confirmReplace && (
              <Alert tone="warning">
                <p className="mb-2">Replace what you've written with a new AI draft?</p>
                <div className="flex gap-2">
                  <Button variant="secondary" onClick={() => void generate()}>Replace it</Button>
                  <Button variant="ghost" onClick={() => setConfirmReplace(false)}>Keep my text</Button>
                </div>
              </Alert>
            )}
            {draftError && <Alert tone="error">{draftError}</Alert>}

            <Textarea
              id="reply"
              rows={10}
              value={replyText}
              onChange={(e) => onReplyChange(e.target.value)}
              maxLength={5000}
              disabled={sending}
              placeholder="Write your reply, or use “Draft with AI” and edit the result."
            />
            <p className="text-xs text-stone-500">
              AI drafts are suggestions. Nothing is sent until you press Send.
              {draftInfo && ` Drafted by ${draftInfo.model}.`}
            </p>

            {draftInfo && draftInfo.warnings.length > 0 && (
              <Alert tone="warning">
                <p className="font-medium">Check before sending</p>
                <ul className="mt-1 list-disc space-y-0.5 pl-5">
                  {draftInfo.warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
                <p className="mt-1 text-xs opacity-80">These refer to the original AI text, not to your later edits.</p>
              </Alert>
            )}
            {draftInfo && draftInfo.verify.length > 0 && (
              <Alert tone="info">
                <p className="font-medium">Worth confirming</p>
                <ul className="mt-1 list-disc space-y-0.5 pl-5">
                  {draftInfo.verify.map((v) => (
                    <li key={v}>{v}</li>
                  ))}
                </ul>
              </Alert>
            )}

            <div className="flex flex-wrap items-center justify-between gap-3">
              {canResolve ? (
                <label className="flex items-center gap-2 text-sm text-stone-700">
                  <input type="checkbox" checked={resolveAfter} onChange={(e) => setResolveAfter(e.target.checked)} disabled={sending} />
                  Mark as resolved after sending
                </label>
              ) : (
                <span />
              )}
              <Button loading={sending} disabled={!replyText.trim()} onClick={() => void sendReply()}>
                Send reply
              </Button>
            </div>
          </div>
        )
      ) : (
        <div className="space-y-3 rounded-md border border-dashed border-amber-400 bg-amber-50 p-3">
          <label htmlFor="note" className="block text-sm font-medium text-amber-900">
            Internal note <span className="font-normal">· never visible to the author</span>
          </label>
          <Textarea id="note" rows={5} value={noteText} onChange={(e) => setNoteText(e.target.value)} maxLength={5000} disabled={savingNote} />
          <Button loading={savingNote} disabled={!noteText.trim()} onClick={() => void saveNote()}>Add internal note</Button>
        </div>
      )}
    </Card>
  )
}