import { authorTheme } from '../components/theme'
import { AppShell, type NavItem } from './AppShell'

const NAV: NavItem[] = [
  { to: '/author/dashboard', label: 'Dashboard' },
  { to: '/author/books', label: 'My Books' },
  { to: '/author/tickets/new', label: 'Submit a Query' },
  { to: '/author/tickets', label: 'My Tickets', end: true },
]

export function AuthorLayout() {
  return <AppShell portalLabel="Author Portal" nav={NAV} theme={authorTheme} />
}