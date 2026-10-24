import re
from decimal import Decimal

from app.core.errors import AppError
from app.db.ids import parse_object_id
from app.db.money import from_d128
from app.schemas.books import BookOut
from app.schemas.dashboard import AuthorDashboard
from app.models.enums import TicketStatus

PUBLISHED_STATUS = "Published & Live"
SORTABLE = {"title", "publication_date", "royalty_pending"}


def book_to_out(b: dict) -> BookOut:
    zero = Decimal("0")
    return BookOut(
        id=str(b["_id"]),
        book_code=b["book_code"],
        title=b["title"],
        isbn=b.get("isbn"),
        genre=b.get("genre"),
        publication_date=b.get("publication_date"),
        status=b["status"],
        is_published=b["status"] == PUBLISHED_STATUS,
        mrp=from_d128(b.get("mrp")),
        royalty_per_copy=from_d128(b.get("royalty_per_copy")),
        total_copies_sold=b.get("total_copies_sold", 0),
        total_royalty_earned=from_d128(b.get("total_royalty_earned")) or zero,
        royalty_paid=from_d128(b.get("royalty_paid")) or zero,
        royalty_pending=from_d128(b.get("royalty_pending")) or zero,
        last_royalty_payout_date=b.get("last_royalty_payout_date"),
        print_partner=b.get("print_partner"),
        available_on=b.get("available_on", []),
    )


async def list_author_books(db, author: dict, q=None, published=None, sort="title", order="asc"):
    flt: dict = {"author_id": author["_id"]}
    if q and q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}  # escaped: no regex injection
        flt["$or"] = [{"title": rx}, {"isbn": rx}, {"genre": rx}]
    if published is True:
        flt["status"] = PUBLISHED_STATUS
    elif published is False:
        flt["status"] = {"$ne": PUBLISHED_STATUS}

    sort_field = sort if sort in SORTABLE else "title"
    cursor = db.books.find(flt).sort([(sort_field, 1 if order == "asc" else -1), ("_id", 1)])
    return [book_to_out(b) for b in await cursor.to_list()]


async def get_author_book(db, author: dict, book_id: str) -> dict:
    oid = parse_object_id(book_id, "Book")
    # Ownership is part of the query: another author's book is simply "not found".
    book = await db.books.find_one({"_id": oid, "author_id": author["_id"]})
    if book is None:
        raise AppError(404, "not_found", "Book not found.")
    return book


async def author_dashboard(db, author: dict) -> AuthorDashboard:
    books = await db.books.find({"author_id": author["_id"]}).to_list()

    def total(field: str) -> Decimal:
        return sum((from_d128(b.get(field)) or Decimal("0") for b in books), Decimal("0"))

    cursor = await db.tickets.aggregate([
        {"$match": {"author_id": author["_id"]}},
        {"$group": {"_id": "$status", "n": {"$sum": 1}}},
    ])
    by_status = {s.value: 0 for s in TicketStatus}
    for row in await cursor.to_list():
        by_status[row["_id"]] = row["n"]

    return AuthorDashboard(
        total_books=len(books),
        published_books=sum(1 for b in books if b["status"] == PUBLISHED_STATUS),
        books_in_production=sum(1 for b in books if b["status"].startswith("In Production")),
        total_royalty_earned=total("total_royalty_earned"),
        royalty_paid=total("royalty_paid"),
        royalty_pending=total("royalty_pending"),
        open_tickets=by_status[TicketStatus.OPEN.value] + by_status[TicketStatus.IN_PROGRESS.value],
        total_tickets=sum(by_status.values()),
        tickets_by_status=by_status,
    )