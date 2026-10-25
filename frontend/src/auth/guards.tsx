import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { ErrorState, PageSpinner } from '../components/ui.tsx'
import { homeFor } from '../lib/routes'
import type { Role } from '../lib/types'
import { useAuth } from './useAuth'

/** UX only: the backend enforces every permission. This just avoids showing pages that would 401/403. */
export function RequireRole({ role }: { role: Role }) {
  const { status, user, retry } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <PageSpinner />
  if (status === 'error') {
    return (
      <div className="mx-auto max-w-md p-8">
        <ErrorState message="We couldn't reach the server to check your session." onRetry={retry} />
      </div>
    )
  }
  if (status === 'anon' || !user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (user.role !== role) return <Navigate to={homeFor(user.role)} replace />
  return <Outlet />
}

export function RootRedirect() {
  const { status, user } = useAuth()
  if (status === 'loading') return <PageSpinner />
  if (status === 'authed' && user) return <Navigate to={homeFor(user.role)} replace />
  return <Navigate to="/login" replace />
}