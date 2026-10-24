from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.models.enums import TicketCategory, TicketPriority, TicketStatus


class TicketCreate(BaseModel):
    # extra="forbid": a client sending author_id, status, priority, etc. gets a 422 (no mass assignment)
    model_config = ConfigDict(extra="forbid")

    book_id: str | None = Field(default=None, max_length=24)  # null = General / Account Level
    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=5000)]

    @field_validator("book_id", mode="before")
    @classmethod
    def empty_book_is_general(cls, v):
        return v or None


class BookRef(BaseModel):
    id: str
    title: str


class MessageOut(BaseModel):
    id: str
    body: str
    created_at: datetime
    from_support: bool
    sender_label: str  # "BookLeaf Support" or "You"


class AuthorTicketListItem(BaseModel):
    ticket_number: int
    display_id: str
    subject: str
    book: BookRef | None
    category: TicketCategory
    priority: TicketPriority
    status: TicketStatus
    created_at: datetime
    updated_at: datetime


class AuthorTicketDetail(AuthorTicketListItem):
    description: str
    messages: list[MessageOut]  # public replies only, oldest first