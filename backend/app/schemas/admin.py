from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.models.enums import (
    ClassificationStatus,
    MessageKind,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from app.schemas.books import BookOut
from app.schemas.tickets import BookRef


class UserRef(BaseModel):
    id: str
    name: str


class AuthorRef(BaseModel):
    id: str
    author_code: str
    name: str
    email: str
    city: str | None = None


class AdminTicketListItem(BaseModel):
    ticket_number: int
    display_id: str
    subject: str
    author: AuthorRef
    book: BookRef | None
    category: TicketCategory
    priority: TicketPriority
    status: TicketStatus
    assignee: UserRef | None
    classification_status: ClassificationStatus
    category_overridden: bool
    priority_overridden: bool
    created_at: datetime
    updated_at: datetime


class AiTriage(BaseModel):
    """The AI's original recommendation, kept separate from the final (possibly overridden) values."""
    ai_category: TicketCategory | None
    ai_priority: TicketPriority | None
    ai_confidence: float | None
    ai_rationale: str | None
    classified_at: datetime | None


class AdminMessageOut(BaseModel):
    id: str
    kind: MessageKind
    body: str
    created_at: datetime
    sender: UserRef
    sender_role: str
    ai_drafted: bool


class AuditOut(BaseModel):
    id: str
    action: str
    old_value: str | None
    new_value: str | None
    actor: UserRef | None  # null = system / AI
    created_at: datetime


class AdminTicketDetail(AdminTicketListItem):
    description: str
    resolved_at: datetime | None
    book_detail: BookOut | None
    ai: AiTriage
    messages: list[AdminMessageOut]  # public AND internal, clearly marked by `kind`
    audit: list[AuditOut]


class TicketPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")  # nothing else can be changed through this endpoint

    status: TicketStatus | None = None
    category: TicketCategory | None = None
    priority: TicketPriority | None = None
    assignee_id: str | None = None  # "me" | admin user id | null (= unassign)

    @model_validator(mode="after")
    def check_fields(self):
        provided = self.model_fields_set
        if not provided:
            raise ValueError("Provide at least one field to update.")
        for f in ("status", "category", "priority"):
            if f in provided and getattr(self, f) is None:
                raise ValueError(f"{f} cannot be null.")
        return self


class NoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class ReplyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
    client_msg_id: str | None = Field(default=None, min_length=8, max_length=64)  # idempotency key
    from_ai_draft: bool = False
    set_status: TicketStatus | None = None  # "send and resolve"


class AdminMetrics(BaseModel):
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    resolved_tickets: int
    closed_tickets: int
    urgent_unresolved: int        # Critical + High that are Open / In Progress
    unassigned_unresolved: int
    assigned_to_me: int
    avg_resolution_hours: float | None  # null until at least one ticket has been resolved
    urgent_queue: list[AdminTicketListItem]     # top 5 by urgency
    longest_waiting: list[AdminTicketListItem]  # 5 oldest unresolved