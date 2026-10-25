import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, ApiError, setUnauthorizedHandler, tokenStore } from '../lib/api'
import type { User } from '../lib/types'
import { AuthContext, type AuthContextValue, type AuthStatus } from './context'

interface State { status: AuthStatus; user: User | null; token: string | null }
const ANON: State = { status: 'anon', user: null, token: null }

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>(() => {
    const token = tokenStore.get()
    return token ? { status: 'loading', user: null, token } : ANON
  })

  // Any 401 on an authenticated request means the session is over.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      tokenStore.clear()
      setState(ANON)
    })
    return () => setUnauthorizedHandler(null)
  }, [])

  // Restore the session on page load: ask the server who the stored token belongs to.
  useEffect(() => {
    if (state.status !== 'loading') return
    const ctrl = new AbortController()
    api.auth.me(ctrl.signal).then(
      (user) => setState({ status: 'authed', user, token: tokenStore.get() }),
      (err: unknown) => {
        if (ctrl.signal.aborted) return
        if (err instanceof ApiError && err.status === 401) return // handler above already cleared the session
        setState((s) => ({ ...s, status: 'error' })) // server unreachable: keep the token, offer a retry
      },
    )
    return () => ctrl.abort()
  }, [state.status])

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.auth.login(email, password)
    tokenStore.set(res.access_token)
    setState({ status: 'authed', user: res.user, token: res.access_token })
    return res.user
  }, [])

  const logout = useCallback(() => {
    tokenStore.clear()
    setState(ANON)
  }, [])

  const retry = useCallback(() => setState((s) => (s.token ? { ...s, status: 'loading' } : s)), [])

  const value = useMemo<AuthContextValue>(() => ({ ...state, login, logout, retry }), [state, login, logout, retry])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}