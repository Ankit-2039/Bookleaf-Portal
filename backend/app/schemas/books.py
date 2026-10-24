from datetime import date

from pydantic import BaseModel

from app.schemas.common import Money


class BookOut(BaseModel):
    id: str
    book_code: str
    title: str
    isbn: str | None
    genre: str | None
    publication_date: date | None   # null while in production
    status: str
    is_published: bool
    mrp: Money | None               # null while in production
    royalty_per_copy: Money | None
    total_copies_sold: int
    total_royalty_earned: Money
    royalty_paid: Money
    royalty_pending: Money
    last_royalty_payout_date: date | None
    print_partner: str | None
    available_on: list[str]