import { useState, type FormEvent } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { Alert, Button, Card, Field, Input, PageSpinner } from '../components/ui'
import { toApiError } from '../lib/api'
import { homeFor } from '../lib/routes'

export function LoginPage() {
  const { status, user, login } = useAuth()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (status === 'loading') return <PageSpinner />
  if (status === 'authed' && user) {
    const from = (location.state as { from?: string } | null)?.from
    return <Navigate to={from && from.startsWith(`/${user.role}`) ? from : homeFor(user.role)} replace />
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (submitting) return
    setSubmitting(true)
    setError(null)
    try {
      await login(email.trim(), password)
    } catch (err) {
      setError(toApiError(err).message)
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-stone-50 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <p className="text-2xl font-semibold text-emerald-800">BookLeaf</p>
          <p className="mt-1 text-sm text-stone-500">Author Support &amp; Communication Portal</p>
        </div>
        <Card className="p-6">
          <h1 className="mb-4 text-lg font-semibold text-stone-900">Sign in</h1>
          <form onSubmit={onSubmit} className="space-y-4">
            {error && <Alert tone="error">{error}</Alert>}
            <Field label="Email" htmlFor="email">
              <Input id="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </Field>
            <Field label="Password" htmlFor="password">
              <Input id="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            </Field>
            <Button type="submit" className="w-full" loading={submitting}>Sign in</Button>
          </form>
        </Card>
        <p className="mt-4 text-center text-xs text-stone-500">Authors and BookLeaf support staff sign in here.</p>
      </div>
    </div>
  )
}