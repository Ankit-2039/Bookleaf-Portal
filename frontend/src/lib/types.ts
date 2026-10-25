export type Role = 'author' | 'admin'
export type TicketStatus = 'Open' | 'In Progress' | 'Resolved' | 'Closed'
export type TicketPriority = 'Critical' | 'High' | 'Medium' | 'Low'
export type TicketCategory =
  | 'Royalty & Payments'
  | 'ISBN & Metadata Issues'
  | 'Printing & Quality'
  | 'Distribution & Availability'
  | 'Book Status & Production Updates'
  | 'General Inquiry'
export type ClassificationStatus = 'pending' | 'ok' | 'failed'

export interface User { id: string; email: string; name: string; role: Role }
export interface TokenResponse { access_token: string; token_type: string; expires_in: number; user: User }
export interface Page<T> { items: T[]; total: number; page: number; page_size: number }

export interface Book {
  id: string
  book_code: string
  title: string
  isbn: string | null
  genre: string | null
  publication_date: string | null
  status: string
  is_published: boolean
  mrp: number | null
  royalty_per_copy: number | null
  total_copies_sold: number
  total_royalty_earned: number
  royalty_paid: number
  royalty_pending: number
  last_royalty_payout_date: string | null
  print_partner: string | null
  available_on: string[]
}

export interface AuthorDashboard {
  total_books: number
  published_books: number
  books_in_production: number
  total_royalty_earned: number
  royalty_paid: number
  royalty_pending: number
  open_tickets: number
  total_tickets: number
  tickets_by_status: Record<string, number>
}

export interface BookRef { id: string; title: string }

export interface AuthorTicketListItem {
  ticket_number: number
  display_id: string
  subject: string
  book: BookRef | null
  category: TicketCategory
  priority: TicketPriority
  status: TicketStatus
  created_at: string
  updated_at: string
}
export interface AuthorMessage {
  id: string
  body: string
  created_at: string
  from_support: boolean
  sender_label: string
}
export interface AuthorTicketDetail extends AuthorTicketListItem {
  description: string
  messages: AuthorMessage[]
}

export interface UserRef { id: string; name: string }
export interface AuthorRef { id: string; author_code: string; name: string; email: string; city: string | null }

export interface AdminTicketListItem {
  ticket_number: number
  display_id: string
  subject: string
  author: AuthorRef
  book: BookRef | null
  category: TicketCategory
  priority: TicketPriority
  status: TicketStatus
  assignee: UserRef | null
  classification_status: ClassificationStatus
  category_overridden: boolean
  priority_overridden: boolean
  created_at: string
  updated_at: string
}
export interface AiTriage {
  ai_category: TicketCategory | null
  ai_priority: TicketPriority | null
  ai_confidence: number | null
  ai_rationale: string | null
  classified_at: string | null
  error_code: string | null
}
export interface AdminMessage {
  id: string
  kind: 'public' | 'internal'
  body: string
  created_at: string
  sender: UserRef
  sender_role: string
  ai_drafted: boolean
}
export interface AuditEvent {
  id: string
  action: string
  old_value: string | null
  new_value: string | null
  actor: UserRef | null
  created_at: string
}
export interface AdminTicketDetail extends AdminTicketListItem {
  description: string
  resolved_at: string | null
  book_detail: Book | null
  ai: AiTriage
  messages: AdminMessage[]
  audit: AuditEvent[]
}
export interface AdminMetrics {
  total_tickets: number
  open_tickets: number
  in_progress_tickets: number
  resolved_tickets: number
  closed_tickets: number
  urgent_unresolved: number
  unassigned_unresolved: number
  assigned_to_me: number
  avg_resolution_hours: number | null
  urgent_queue: AdminTicketListItem[]
  longest_waiting: AdminTicketListItem[]
}
export interface DraftResponse {
  draft: string
  verify_before_sending: string[]
  warnings: string[]
  model: string
  generated_at: string
}

// Request payloads
export interface TicketCreateBody { book_id: string | null; subject: string; description: string }
export interface TicketPatchBody {
  status?: TicketStatus
  category?: TicketCategory
  priority?: TicketPriority
  assignee_id?: string | null // 'me' | admin id | null (= unassign)
}
export interface ReplyBody {
  body: string
  client_msg_id?: string
  from_ai_draft?: boolean
  set_status?: TicketStatus
}

// Query shapes
export interface AuthorBooksQuery {
  q?: string
  published?: boolean
  sort?: 'title' | 'publication_date' | 'royalty_pending'
  order?: 'asc' | 'desc'
}
export interface AuthorTicketsQuery { status?: TicketStatus; page?: number; page_size?: number }
export interface AdminQueueQuery {
  status?: TicketStatus[]
  category?: TicketCategory[]
  priority?: TicketPriority[]
  assignee?: string
  date_from?: string
  date_to?: string
  q?: string
  sort?: 'urgency' | 'newest' | 'oldest' | 'updated'
  page?: number
  page_size?: number
}