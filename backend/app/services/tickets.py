from pymongo import ReturnDocument

from app.api.deps import CurrentUser
from app.core.clock import utcnow
from app.core.errors import AppError
from app.db.ids import parse_object_id
from app.models.enums import (
    PRIORITY_RANK,
    ClassificationStatus,
    MessageKind,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from app.schemas.tickets import (
    AuthorTicketDetail,
    AuthorTicketListItem,
    BookRef,
    MessageOut,
    TicketCreate,
)


def display_id(n: int) -> str:
    return f"TKT-{n}"


async def next_ticket_number(db) -> int:
    """Atomic counter: concurrent submissions can never receive the same number."""
    doc = await db.counters.find_one_and_update(
        {"_id": "ticket"}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER
    )
    return doc["seq"]


async def create_ticket(db, author: dict, body: TicketCreate) -> tuple[dict, dict | None]:
    book = None
    if body.book_id:
        oid = parse_object_id(body.book_id, "Book")
        book = await db.books.find_one({"_id": oid, "author_id": author["_id"]})
        if book is None:
            raise AppError(404, "not_found", "Book not found.")

    now = utcnow()
    doc = {
        "ticket_number": await next_ticket_number(db),
        "author_id": author["_id"],          # from the token, never from the request body
        "book_id": book["_id"] if book else None,
        "subject": body.subject,
        "description": body.description,
        "status": TicketStatus.OPEN.value,
        # Placeholders until AI triage runs (Step 7). Clearly marked as pending.
        "category": TicketCategory.GENERAL.value,
        "priority": TicketPriority.MEDIUM.value,
        "priority_rank": PRIORITY_RANK[TicketPriority.MEDIUM],
        "classification_status": ClassificationStatus.PENDING.value,
        "ai_category": None,
        "ai_priority": None,
        "ai_confidence": None,
        "ai_rationale": None,
        "classified_at": None,
        "category_overridden": False,
        "priority_overridden": False,
        "assignee_id": None,
        "created_at": now,
        "updated_at": now,
        "resolved_at": None,
    }
    result = await db.tickets.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc, book


async def get_author_ticket(db, author: dict, ticket_number: int) -> dict:
    # Ownership in the filter: someone else's ticket is indistinguishable from a missing one.
    t = await db.tickets.find_one({"ticket_number": ticket_number, "author_id": author["_id"]})
    if t is None:
        raise AppError(404, "not_found", "Ticket not found.")
    return t


async def get_public_messages(db, ticket_oid) -> list[dict]:
    """The ONLY message query used by author endpoints. Internal notes can never come through it."""
    cursor = db.ticket_messages.find(
        {"ticket_id": ticket_oid, "kind": MessageKind.PUBLIC.value}
    ).sort([("created_at", 1), ("_id", 1)])
    return await cursor.to_list()


def _list_item_fields(t: dict, book: dict | None) -> dict:
    return {
        "ticket_number": t["ticket_number"],
        "display_id": display_id(t["ticket_number"]),
        "subject": t["subject"],
        "book": BookRef(id=str(book["_id"]), title=book["title"]) if book else None,
        "category": t["category"],
        "priority": t["priority"],
        "status": t["status"],
        "created_at": t["created_at"],
        "updated_at": t["updated_at"],
    }


def to_author_detail(t: dict, book: dict | None, messages: list[dict], viewer: CurrentUser) -> AuthorTicketDetail:
    msgs = [
        MessageOut(
            id=str(m["_id"]),
            body=m["body"],
            created_at=m["created_at"],
            from_support=m["sender_id"] != viewer.oid,
            sender_label="You" if m["sender_id"] == viewer.oid else "BookLeaf Support",
        )
        for m in messages
    ]
    return AuthorTicketDetail(**_list_item_fields(t, book), description=t["description"], messages=msgs)


async def list_author_tickets(db, author: dict, status: TicketStatus | None, page: int, page_size: int):
    flt: dict = {"author_id": author["_id"]}
    if status:
        flt["status"] = status.value

    total = await db.tickets.count_documents(flt)
    cursor = (
        db.tickets.find(flt)
        .sort([("updated_at", -1), ("_id", -1)])
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    tickets = await cursor.to_list()

    # One batched lookup for book titles instead of one query per ticket.
    book_ids = list({t["book_id"] for t in tickets if t.get("book_id")})
    books = {}
    if book_ids:
        async for b in db.books.find({"_id": {"$in": book_ids}}, {"title": 1}):
            books[b["_id"]] = b

    items = [AuthorTicketListItem(**_list_item_fields(t, books.get(t.get("book_id")))) for t in tickets]
    return items, total