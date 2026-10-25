import type { Role } from './types'

export const homeFor = (role: Role): string => (role === 'admin' ? '/admin/dashboard' : '/author/dashboard')