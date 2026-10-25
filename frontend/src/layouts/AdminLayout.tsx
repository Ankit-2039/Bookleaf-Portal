import { adminTheme } from '../components/theme'
import { AppShell, type NavItem } from './AppShell'

const NAV: NavItem[] = [
  { to: '/admin/dashboard', label: 'Dashboard' },
  { to: '/admin/tickets', label: 'Ticket Queue' },
]

export function AdminLayout() {
  return <AppShell portalLabel="Support Operations" nav={NAV} theme={adminTheme} />
}