import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthProvider'
import { RequireRole, RootRedirect } from './auth/guards'
import { AdminLayout } from './layouts/AdminLayout'
import { AuthorLayout } from './layouts/AuthorLayout'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PlaceholderPage } from './pages/PlaceholderPage'

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
              <Route path="/author/dashboard" element={<PlaceholderPage title="Dashboard" />} />
              <Route path="/author/books" element={<PlaceholderPage title="My Books" />} />
              <Route path="/author/tickets" element={<PlaceholderPage title="My Tickets" />} />
              <Route path="/author/tickets/new" element={<PlaceholderPage title="Submit a Support Query" />} />
              <Route path="/author/tickets/:ticketNumber" element={<PlaceholderPage title="Ticket" />} />
            </Route>
          </Route>

          <Route element={<RequireRole role="admin" />}>
            <Route element={<AdminLayout />}>
              <Route path="/admin" element={<Navigate to="/admin/dashboard" replace />} />
              <Route path="/admin/dashboard" element={<PlaceholderPage title="Admin Dashboard" />} />
              <Route path="/admin/tickets" element={<PlaceholderPage title="Ticket Queue" />} />
              <Route path="/admin/tickets/:ticketNumber" element={<PlaceholderPage title="Ticket" />} />
            </Route>
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}