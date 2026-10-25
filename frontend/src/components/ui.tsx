import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { PRIORITY_STYLES, STATUS_STYLES } from '../lib/styles'
import type { TicketPriority, TicketStatus } from '../lib/types'
import { useTheme } from './theme'

export function Spinner({ className = 'h-5 w-5' }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  )
}

export function PageSpinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div role="status" className="flex min-h-[40vh] items-center justify-center gap-3 text-stone-500">
      <Spinner className="h-6 w-6" />
      <span className="text-sm">{label}</span>
    </div>
  )
}

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost'
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  loading?: boolean
}

export function Button({ variant = 'primary', loading = false, disabled, className = '', children, type = 'button', ...rest }: ButtonProps) {
  const theme = useTheme()
  const styles: Record<Variant, string> = {
    primary: theme.primary,
    secondary: 'bg-white text-stone-800 ring-1 ring-inset ring-stone-300 hover:bg-stone-50 focus-visible:outline-stone-500',
    danger: 'bg-red-600 text-white hover:bg-red-700 focus-visible:outline-red-600',
    ghost: 'text-stone-700 hover:bg-stone-100 focus-visible:outline-stone-500',
  }
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`inline-flex items-center justify-center gap-2 rounded-md px-3.5 py-2 text-sm font-medium shadow-sm transition focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60 ${styles[variant]} ${className}`}
      {...rest}
    >
      {loading && <Spinner className="h-4 w-4" />}
      {children}
    </button>
  )
}

const inputBase =
  'block w-full rounded-md border bg-white px-3 py-2 text-sm text-stone-900 shadow-sm outline-none placeholder:text-stone-400 disabled:bg-stone-100 disabled:text-stone-500'

function useFieldClass(invalid: boolean | undefined) {
  const theme = useTheme()
  return `${inputBase} ${invalid ? 'border-red-500 focus:ring-2 focus:ring-red-500/25' : `border-stone-300 ${theme.focus}`}`
}

type WithInvalid<T> = T & { invalid?: boolean }

export function Input({ invalid, className = '', ...rest }: WithInvalid<InputHTMLAttributes<HTMLInputElement>>) {
  const base = useFieldClass(invalid)
  return (
    <input
      aria-invalid={invalid || undefined}
      aria-describedby={invalid && rest.id ? `${rest.id}-error` : undefined}
      className={`${base} ${className}`}
      {...rest}
    />
  )
}

export function Textarea({ invalid, className = '', ...rest }: WithInvalid<TextareaHTMLAttributes<HTMLTextAreaElement>>) {
  const base = useFieldClass(invalid)
  return (
    <textarea
      aria-invalid={invalid || undefined}
      aria-describedby={invalid && rest.id ? `${rest.id}-error` : undefined}
      className={`${base} ${className}`}
      {...rest}
    />
  )
}

export function Select({ invalid, className = '', children, ...rest }: WithInvalid<SelectHTMLAttributes<HTMLSelectElement>>) {
  const base = useFieldClass(invalid)
  return (
    <select
      aria-invalid={invalid || undefined}
      aria-describedby={invalid && rest.id ? `${rest.id}-error` : undefined}
      className={`${base} ${className}`}
      {...rest}
    >
      {children}
    </select>
  )
}

export function Field({ label, htmlFor, error, hint, children }: { label: string; htmlFor: string; error?: string; hint?: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-stone-700">{label}</label>
      {children}
      {hint && !error && <p className="text-xs text-stone-500">{hint}</p>}
      {error && <p id={`${htmlFor}-error`} role="alert" className="text-xs text-red-600">{error}</p>}
    </div>
  )
}

export function Card({ className = '', children }: { className?: string; children: ReactNode }) {
  return <div className={`rounded-lg border border-stone-200 bg-white shadow-sm ${className}`}>{children}</div>
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-stone-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-stone-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  )
}

type Tone = 'info' | 'error' | 'success' | 'warning'
const ALERT_STYLES: Record<Tone, string> = {
  info: 'border-blue-200 bg-blue-50 text-blue-800',
  error: 'border-red-200 bg-red-50 text-red-800',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  warning: 'border-amber-200 bg-amber-50 text-amber-900',
}

export function Alert({ tone = 'info', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <div role={tone === 'error' ? 'alert' : 'status'} className={`rounded-md border px-3 py-2 text-sm ${ALERT_STYLES[tone]}`}>
      {children}
    </div>
  )
}

export function StatCard({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-stone-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-stone-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-stone-500">{hint}</p>}
    </Card>
  )
}

export function EmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-stone-300 bg-white px-6 py-12 text-center">
      <p className="font-medium text-stone-800">{title}</p>
      {description && <p className="mx-auto mt-1 max-w-md text-sm text-stone-500">{description}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  )
}

export function ErrorState({ title = 'Something went wrong', message, onRetry }: { title?: string; message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-6 py-8 text-center">
      <p className="font-medium text-red-800">{title}</p>
      <p className="mt-1 text-sm text-red-700">{message}</p>
      {onRetry && (
        <div className="mt-4 flex justify-center">
          <Button variant="secondary" onClick={onRetry}>Try again</Button>
        </div>
      )}
    </div>
  )
}

const BADGE = 'inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset'

export function StatusBadge({ status }: { status: TicketStatus }) {
  return <span className={`${BADGE} ${STATUS_STYLES[status]}`}>{status}</span>
}

export function PriorityBadge({ priority }: { priority: TicketPriority }) {
  return <span className={`${BADGE} ${PRIORITY_STYLES[priority]}`}>{priority}</span>
}

export function Pill({ children }: { children: ReactNode }) {
  return <span className={`${BADGE} bg-stone-100 text-stone-700 ring-stone-200`}>{children}</span>
}