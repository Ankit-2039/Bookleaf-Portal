import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthProvider'
import { RequireRole, RootRedirect } from './auth/guards'
import { AdminLayout } from './layouts/AdminLayout'
import { AuthorLayout } from './layouts/AuthorLayout'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PlaceholderPage } from './pages/PlaceholderPage'
import { BooksPage } from './pages/author/BooksPage'
import { DashboardPage } from './pages/author/DashboardPage'
import { NewTicketPage } from './pages/author/NewTicketPage'
import { TicketDetailPage } from './pages/author/TicketDetailPage'
import { TicketsPage } from './pages/author/TicketsPage'
import { AdminDashboardPage } from './pages/admin/DashboardPage'
import { QueuePage } from './pages/admin/QueuePage'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<RootRedirect />} />
          <Route path="/login" element={<LoginPage />} />

          <Route element={<RequireRole role="author" />}>
            <Route element={<AuthorLayout />}>
              <Route path="/author" element={<Navigate to="/author/dashboard" replace />} />
              <Route path="/author/dashboard" element={<DashboardPage />} />
              <Route path="/author/books" element={<BooksPage />} />
              <Route path="/author/tickets" element={<TicketsPage />} />
              <Route path="/author/tickets/new" element={<NewTicketPage />} />
              <Route path="/author/tickets/:ticketNumber" element={<TicketDetailPage />} />
            </Route>
          </Route>

          <Route element={<RequireRole role="admin" />}>
            <Route element={<AdminLayout />}>
              <Route path="/admin" element={<Navigate to="/admin/dashboard" replace />} />
              <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
              <Route path="/admin/tickets" element={<QueuePage />} />
              <Route path="/admin/tickets/:ticketNumber" element={<PlaceholderPage title="Ticket" />} />
            </Route>
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}