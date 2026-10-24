from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from app.models.enums import TicketCategory, TicketPriority


@dataclass(frozen=True)
class BookFacts:
    title: str
    status: str
    isbn: str | None = None
    publication_date: date | None = None
    mrp: Decimal | None = None
    copies_sold: int = 0
    royalty_earned: Decimal = Decimal("0")
    royalty_paid: Decimal = Decimal("0")
    royalty_pending: Decimal = Decimal("0")
    last_payout_date: date | None = None
    print_partner: str | None = None
    available_on: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HistoryMessage:
    sender: str       # "BookLeaf" (public replies only; internal notes are never included)
    body: str
    sent_on: date


@dataclass
class TicketContext:
    ticket_number: int
    subject: str
    description: str
    status: str
    category: TicketCategory
    priority: TicketPriority
    created_at: datetime
    author_first_name: str
    book: BookFacts | None
    today: date
    author_total_pending: Decimal | None = None
    history: list[HistoryMessage] = field(default_factory=list)