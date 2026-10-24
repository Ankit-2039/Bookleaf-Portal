from pydantic import BaseModel

from app.schemas.common import Money


class AuthorDashboard(BaseModel):
    total_books: int
    published_books: int
    books_in_production: int
    total_royalty_earned: Money
    royalty_paid: Money
    royalty_pending: Money
    open_tickets: int            # Open + In Progress
    total_tickets: int
    tickets_by_status: dict[str, int]