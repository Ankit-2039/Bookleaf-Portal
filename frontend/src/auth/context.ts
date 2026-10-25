import { createContext } from 'react'
import type { User } from '../lib/types'

export type AuthStatus = 'loading' | 'authed' | 'anon' | 'error'

export interface AuthContextValue {
  status: AuthStatus
  user: User | null
  token: string | null
  login: (email: string, password: string) => Promise<User>
  logout: () => void
  retry: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)