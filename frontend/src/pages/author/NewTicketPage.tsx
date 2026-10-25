import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Alert, Button, Card, Field, Input, PageHeader, Select, Textarea } from '../../components/ui'
import { api, fieldErrors, toApiError } from '../../lib/api'
import { useResource } from '../../lib/useResource'

const SUBJECT_MIN = 3
const SUBJECT_MAX = 200
const DESC_MIN = 10
const DESC_MAX = 5000

export function NewTicketPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const books = useResource('author-books-select', (s) => api.author.books(undefined, s))

  const [bookId, setBookId] = useState(() => params.get('book') ?? '')
  const [subject, setSubject] = useState('')
  const [description, setDescription] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  function validate(): Record<string, string> {
    const found: Record<string, string> = {}
    const s = subject.trim()
    const d = description.trim()
    if (s.length < SUBJECT_MIN) found.subject = `Please enter a subject (at least ${SUBJECT_MIN} characters).`
    if (d.length < DESC_MIN) found.description = `Please describe your query in a little more detail (at least ${DESC_MIN} characters).`
    if (bookId && books.data && !books.data.some((b) => b.id === bookId)) {
      found.book_id = 'Choose one of your books, or General / Account Level.'
    }
    return found
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (submitting) return
    const found = validate()
    setErrors(found)
    setFormError(null)
    if (Object.keys(found).length > 0) return

    setSubmitting(true)
    try {
      const ticket = await api.author.createTicket({
        book_id: bookId || null,
        subject: subject.trim(),
        description: description.trim(),
      })
      navigate(`/author/tickets/${ticket.ticket_number}`, { replace: true, state: { created: true } })
    } catch (err) {
      const fe = fieldErrors(err)
      setErrors(fe)
      setFormError(Object.keys(fe).length > 0 ? 'Please fix the highlighted fields.' : toApiError(err).message)
      setSubmitting(false)
    }
  }

  return (
    <>
      <PageHeader title="Submit a Support Query" subtitle="Tell us what's happening and our team will respond here." />

      <Card className="max-w-2xl p-6">
        <form onSubmit={onSubmit} noValidate className="space-y-5">
          {formError && <Alert tone="error">{formError}</Alert>}
          {books.error && (
            <Alert tone="warning">We couldn't load your books, but you can still submit a general query.</Alert>
          )}

          <Field label="Which book is this about?" htmlFor="book" error={errors.book_id}>
            <Select id="book" value={bookId} onChange={(e) => setBookId(e.target.value)} invalid={!!errors.book_id} disabled={submitting}>
              <option value="">General / Account Level</option>
              {books.data?.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.title}
                  {b.is_published ? '' : ' (in production)'}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Subject" htmlFor="subject" error={errors.subject}>
            <Input
              id="subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              maxLength={SUBJECT_MAX}
              invalid={!!errors.subject}
              disabled={submitting}
              placeholder="e.g. I haven't received my royalty"
            />
          </Field>

          <Field
            label="Details"
            htmlFor="description"
            error={errors.description}
            hint="Include dates, amounts or what you've already tried. We sort your query by topic and urgency automatically."
          >
            <Textarea
              id="description"
              rows={7}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={DESC_MAX}
              invalid={!!errors.description}
              disabled={submitting}
            />
            <p className="text-right text-xs text-stone-400">{description.length}/{DESC_MAX}</p>
          </Field>

          <Field
            label="Attachments"
            htmlFor="attachments"
            hint="File uploads aren't available yet. Describe the issue above; if photos are needed (for example for a print defect), our team will tell you how to share them."
          >
            <Input id="attachments" type="file" disabled />
          </Field>

          <div className="flex gap-3">
            <Button type="submit" loading={submitting}>Submit query</Button>
            <Button variant="ghost" onClick={() => navigate(-1)} disabled={submitting}>Cancel</Button>
          </div>
        </form>
      </Card>
    </>
  )
}