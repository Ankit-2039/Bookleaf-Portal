import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { ThemeContext, type Theme } from '../components/theme'
import { Button } from '../components/ui'
import { useRealtime } from '../realtime/hooks'
import { RealtimeProvider } from '../realtime/RealtimeProvider'

export interface NavItem { to: string; label: string; end?: boolean }
interface ShellProps { portalLabel: string; nav: NavItem[]; theme: Theme }

function ConnectionBadge() {
  const { status } = useRealtime()
  const map = {
    connected: ['bg-emerald-500', 'Live updates on'],
    connecting: ['bg-amber-400', 'Connecting…'],
    disconnected: ['bg-red-500', 'Offline: refreshing every 10 s'],
  } as const
  const [dot, text] = map[status]
  return (
    <div role="status" className="flex items-center gap-2 text-xs">
      <span className={`h-2 w-2 rounded-full ${dot}`} aria-hidden="true" />
      {text}
    </div>
  )
}

function ShellInner({ portalLabel, nav, theme }: ShellProps) {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-stone-50">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:text-sm">
        Skip to content
      </a>

      {open && <div className="fixed inset-0 z-20 bg-black/40 md:hidden" onClick={() => setOpen(false)} aria-hidden="true" />}

      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-64 shrink-0 flex-col border-r transition-transform md:static md:translate-x-0 ${theme.sidebar} ${theme.sidebarBorder} ${open ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <div className={`border-b px-5 py-5 ${theme.sidebarBorder}`}>
          <p className={`text-lg font-semibold ${theme.brand}`}>BookLeaf</p>
          <p className={`text-xs ${theme.sidebarMuted}`}>{portalLabel}</p>
        </div>

        <nav aria-label="Main" className="flex-1 space-y-1 px-3 py-4">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setOpen(false)}
              className={({ isActive }) => `block rounded-md px-3 py-2 text-sm font-medium ${isActive ? theme.navActive : theme.navIdle}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className={`space-y-3 border-t px-5 py-4 ${theme.sidebarBorder}`}>
          <ConnectionBadge />
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{user?.name}</p>
            <p className={`truncate text-xs ${theme.sidebarMuted}`}>{user?.email}</p>
          </div>
          <Button variant="secondary" className="w-full" onClick={logout}>Sign out</Button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-stone-200 bg-white px-4 py-3 md:hidden">
          <button
            type="button"
            onClick={() => setOpen(true)}
            aria-label="Open menu"
            aria-expanded={open}
            className="rounded-md p-2 text-stone-700 hover:bg-stone-100"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" />
            </svg>
          </button>
          <span className="font-semibold text-stone-900">BookLeaf</span>
          <span className="text-xs text-stone-500">{portalLabel}</span>
        </header>

        <main id="main" className="flex-1 p-4 md:p-8">
          <div className="mx-auto max-w-6xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}

export function AppShell(props: ShellProps) {
  return (
    <ThemeContext.Provider value={props.theme}>
      <RealtimeProvider>
        <ShellInner {...props} />
      </RealtimeProvider>
    </ThemeContext.Provider>
  )
}