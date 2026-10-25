import type {
  AdminMetrics, AdminMessage, AdminQueueQuery, AdminTicketDetail, AdminTicketListItem, AuthorBooksQuery,
  AuthorDashboard, AuthorTicketDetail, AuthorTicketListItem, AuthorTicketsQuery, Book, DraftResponse, Page,
  ReplyBody, TicketCreateBody, TicketPatchBody, TokenResponse, User, UserRef,
} from './types'

const BASE = ((import.meta.env.VITE_API_URL as string | undefined) ?? '').replace(/\/$/, '')
const PREFIX = '/api/v1'
const TOKEN_KEY = 'bookleaf.token'

// ---- token storage (localStorage with an in-memory fallback) ----
let memoryToken: string | null = null
export const tokenStore = {
  get(): string | null {
    if (memoryToken) return memoryToken
    try {
      return localStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set(token: string): void {
    memoryToken = token
    try {
      localStorage.setItem(TOKEN_KEY, token)
    } catch {
      /* storage unavailable: the in-memory copy still works for this tab */
    }
  },
  clear(): void {
    memoryToken = null
    try {
      localStorage.removeItem(TOKEN_KEY)
    } catch {
      /* ignore */
    }
  },
}

// ---- errors ----
export interface FieldDetail { field: string; message: string }

export class ApiError extends Error {
  status: number
  code: string
  details: FieldDetail[]
  retryAfter: number | null

  constructor(status: number, code: string, message: string, details: FieldDetail[] = [], retryAfter: number | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
    this.retryAfter = retryAfter
  }
}

export function toApiError(err: unknown): ApiError {
  if (err instanceof ApiError) return err
  return new ApiError(0, 'unexpected', 'Something went wrong. Please try again.')
}

/** Validation errors keyed by field name, ready for form display. */
export function fieldErrors(err: unknown): Record<string, string> {
  const out: Record<string, string> = {}
  for (const d of toApiError(err).details) out[d.field] = d.message
  return out
}

function parseError(res: Response, data: unknown): ApiError {
  const header = Number(res.headers.get('retry-after'))
  const retryAfter = Number.isFinite(header) && header > 0 ? header : null
  const e = (data as { error?: { code?: unknown; message?: unknown; details?: unknown } } | null)?.error
  const code = typeof e?.code === 'string' ? e.code : 'http_error'
  const message = typeof e?.message === 'string' ? e.message : `Request failed (${res.status}).`
  const details: FieldDetail[] = Array.isArray(e?.details)
    ? (e.details as unknown[]).filter(
        (d): d is FieldDetail =>
          !!d && typeof (d as FieldDetail).field === 'string' && typeof (d as FieldDetail).message === 'string',
      )
    : []
  return new ApiError(res.status, code, message, details, retryAfter)
}

// ---- transport ----
let onUnauthorized: (() => void) | null = null
export function setUnauthorizedHandler(fn: (() => void) | null): void {
  onUnauthorized = fn
}

function buildQuery(q?: object): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(q ?? {})) {
    if (value === undefined || value === null || value === '') continue
    if (Array.isArray(value)) value.forEach((v) => params.append(key, String(v)))
    else params.append(key, String(value))
  }
  const s = params.toString()
  return s ? `?${s}` : ''
}

interface RequestOptions { body?: unknown; query?: object; signal?: AbortSignal; auth?: boolean }

async function request<T>(method: string, path: string, opts: RequestOptions = {}): Promise<T> {
  const token = opts.auth === false ? null : tokenStore.get()
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`

  let res: Response
  try {
    res = await fetch(`${BASE}${PREFIX}${path}${buildQuery(opts.query)}`, {
      method,
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: opts.signal,
    })
  } catch (e) {
    if (opts.signal?.aborted) throw e
    throw new ApiError(0, 'network_error', "Can't reach the server. Check your connection and try again.")
  }

  if (res.status === 204) return undefined as T
  let data: unknown = null
  try {
    data = await res.json()
  } catch {
    /* body was not JSON */
  }

  if (!res.ok) {
    if (res.status === 401 && token) onUnauthorized?.() // the session is over: one central place handles it
    throw parseError(res, data)
  }
  return data as T
}

// ---- endpoints ----
export const api = {
  auth: {
    login: (email: string, password: string) =>
      request<TokenResponse>('POST', '/auth/login', { body: { email, password }, auth: false }),
    me: (signal?: AbortSignal) => request<User>('GET', '/auth/me', { signal }),
  },
  author: {
    dashboard: (signal?: AbortSignal) => request<AuthorDashboard>('GET', '/author/dashboard', { signal }),
    books: (query?: AuthorBooksQuery, signal?: AbortSignal) => request<Book[]>('GET', '/author/books', { query, signal }),
    book: (id: string, signal?: AbortSignal) => request<Book>('GET', `/author/books/${id}`, { signal }),
    tickets: (query?: AuthorTicketsQuery, signal?: AbortSignal) =>
      request<Page<AuthorTicketListItem>>('GET', '/author/tickets', { query, signal }),
    ticket: (n: number, signal?: AbortSignal) => request<AuthorTicketDetail>('GET', `/author/tickets/${n}`, { signal }),
    createTicket: (body: TicketCreateBody) => request<AuthorTicketDetail>('POST', '/author/tickets', { body }),
  },
  admin: {
    metrics: (signal?: AbortSignal) => request<AdminMetrics>('GET', '/admin/metrics', { signal }),
    admins: (signal?: AbortSignal) => request<UserRef[]>('GET', '/admin/admins', { signal }),
    tickets: (query?: AdminQueueQuery, signal?: AbortSignal) =>
      request<Page<AdminTicketListItem>>('GET', '/admin/tickets', { query, signal }),
    ticket: (n: number, signal?: AbortSignal) => request<AdminTicketDetail>('GET', `/admin/tickets/${n}`, { signal }),
    patchTicket: (n: number, body: TicketPatchBody) => request<AdminTicketDetail>('PATCH', `/admin/tickets/${n}`, { body }),
    addNote: (n: number, body: string) => request<AdminMessage>('POST', `/admin/tickets/${n}/notes`, { body: { body } }),
    reply: (n: number, body: ReplyBody) => request<AdminMessage>('POST', `/admin/tickets/${n}/replies`, { body }),
    draft: (n: number) => request<DraftResponse>('POST', `/admin/tickets/${n}/draft`),
    retriage: (n: number) => request<AdminTicketDetail>('POST', `/admin/tickets/${n}/triage`),
  },
}