import logging
from datetime import date, timedelta
from decimal import Decimal

from app.ai.client import AIClient
from app.ai.context import BookFacts, HistoryMessage, TicketContext
from app.ai.deps import get_ai_client
from app.ai.drafting import DraftOutcome, draft_response
from app.ai.errors import AIError
from app.ai.schemas import TriageResult
from app.ai.triage import triage_ticket
from app.core.clock import utcnow
from app.core.errors import AppError
from app.db import mongo
from app.db.money import from_d128
from app.models.enums import (
    PRIORITY_RANK,
    ClassificationStatus,
    MessageKind,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)

logger = logging.getLogger("bookleaf.ai")

HISTORY_LIMIT = 6
DRAFTS_PER_TICKET_PER_HOUR = 10


# ---------------------------------------------------------------- context

def _to_date(v):
    if v is None or isinstance(v, date):
        return v
    return date.fromisoformat(v)  # dataset dates are stored as "YYYY-MM-DD"


def book_facts(b: dict) -> BookFacts:
    zero = Decimal("0")
    return BookFacts(
        title=b["title"],
        status=b["status"],
        isbn=b.get("isbn"),
        publication_date=_to_date(b.get("publication_date")),
        mrp=from_d128(b.get("mrp")),
        copies_sold=b.get("total_copies_sold", 0),
        royalty_earned=from_d128(b.get("total_royalty_earned")) or zero,
        royalty_paid=from_d128(b.get("royalty_paid")) or zero,
        royalty_pending=from_d128(b.get("royalty_pending")) or zero,
        last_payout_date=_to_date(b.get("last_royalty_payout_date")),
        print_partner=b.get("print_partner"),
        available_on=list(b.get("available_on", [])),
    )


async def build_context(db, ticket: dict) -> TicketContext:
    """Only what the model needs: this ticket, its book, the author's first name and the last few
    PUBLIC replies. Internal notes are excluded by the explicit kind filter below."""
    author = await db.authors.find_one({"_id": ticket["author_id"]})
    user = await db.users.find_one({"_id": author["user_id"]}, {"name": 1})
    first_name = (user["name"].split() or ["there"])[0]
    book = await db.books.find_one({"_id": ticket["book_id"]}) if ticket.get("book_id") else None

    category = TicketCategory(ticket["category"])
    reliable = ticket.get("classification_status") == ClassificationStatus.OK.value or ticket.get(
        "category_overridden", False
    )

    total_pending = None
    if category == TicketCategory.ROYALTY or not reliable:
        books = await db.books.find({"author_id": author["_id"]}, {"royalty_pending": 1}).to_list()
        total_pending = sum((from_d128(b.get("royalty_pending")) or Decimal("0") for b in books), Decimal("0"))

    cursor = (
        db.ticket_messages.find({"ticket_id": ticket["_id"], "kind": MessageKind.PUBLIC.value})
        .sort([("created_at", -1), ("_id", -1)])
        .limit(HISTORY_LIMIT)
    )
    recent = list(reversed(await cursor.to_list()))

    return TicketContext(
        ticket_number=ticket["ticket_number"],
        subject=ticket["subject"],
        description=ticket["description"],
        status=ticket["status"],
        category=category,
        priority=TicketPriority(ticket["priority"]),
        created_at=ticket["created_at"],
        author_first_name=first_name,
        book=book_facts(book) if book else None,
        today=utcnow().date(),
        author_total_pending=total_pending,
        history=[HistoryMessage("BookLeaf", m["body"], m["created_at"].date()) for m in recent],
        category_reliable=reliable,
    )


# ---------------------------------------------------------------- triage

async def apply_triage(db, ticket: dict, result: TriageResult) -> None:
    now = utcnow()
    oid = ticket["_id"]

    # 1) The AI's recommendation is always stored, separately from the final values.
    await db.tickets.update_one({"_id": oid}, {"$set": {
        "ai_category": result.category.value,
        "ai_priority": result.priority.value,
        "ai_confidence": result.confidence,
        "ai_rationale": result.rationale,
        "classified_at": now,
        "classification_status": ClassificationStatus.OK.value,
        "ai_error": None,
    }})
    # 2) Final values are written ONLY if the admin hasn't overridden them. The condition is part of
    #    the update itself, so an override that lands while the LLM call was running still wins.
    await db.tickets.update_one(
        {"_id": oid, "category_overridden": {"$ne": True}},
        {"$set": {"category": result.category.value}},
    )
    await db.tickets.update_one(
        {"_id": oid, "priority_overridden": {"$ne": True}},
        {"$set": {"priority": result.priority.value, "priority_rank": PRIORITY_RANK[result.priority]}},
    )
    # updated_at is deliberately not touched: AI triage must not reorder the author's ticket list.
    await db.audit_events.insert_one({
        "ticket_id": oid,
        "actor_id": None,  # system / AI
        "action": "ai_triaged",
        "old_value": f"{ticket['category']} / {ticket['priority']}",
        "new_value": f"{result.category.value} / {result.priority.value}",
        "created_at": now,
    })


async def _mark_failed(db, oid, code: str) -> None:
    # Never downgrade a ticket that was already triaged successfully.
    await db.tickets.update_one(
        {"_id": oid, "classification_status": {"$ne": ClassificationStatus.OK.value}},
        {"$set": {"classification_status": ClassificationStatus.FAILED.value, "ai_error": code}},
    )


async def run_triage(db, ticket_oid, client: AIClient, *, force: bool = False) -> TriageResult | None:
    """Raises AIError on failure (after recording it). Skips already-classified tickets unless forced."""
    ticket = await db.tickets.find_one({"_id": ticket_oid})
    if ticket is None:
        return None
    if not force and ticket.get("classification_status") == ClassificationStatus.OK.value:
        return None  # no repeated spend
    ctx = await build_context(db, ticket)
    try:
        result = await triage_ticket(client, ctx, ticket_id=ticket_oid)
    except AIError as e:
        await _mark_failed(db, ticket_oid, e.code)
        raise
    await apply_triage(db, ticket, result)
    return result


async def triage_in_background(ticket_oid) -> None:
    """Runs after the HTTP response is sent. Must never raise."""
    try:
        await run_triage(mongo.get_db(), ticket_oid, get_ai_client())
    except AIError as e:
        logger.warning("Background triage failed for ticket %s: %s", ticket_oid, e.code)
    except Exception:
        logger.exception("Unexpected error in background triage for ticket %s", ticket_oid)


# ---------------------------------------------------------------- drafting

async def generate_draft(db, ticket: dict, client: AIClient) -> DraftOutcome:
    if ticket["status"] == TicketStatus.CLOSED.value:
        raise AppError(409, "ticket_closed", "Closed tickets cannot receive replies, so no draft is generated.")

    recent = await db.ai_calls.count_documents({
        "ticket_id": ticket["_id"], "purpose": "draft", "status": "ok",
        "created_at": {"$gte": utcnow() - timedelta(hours=1)},
    })
    if recent >= DRAFTS_PER_TICKET_PER_HOUR:
        raise AppError(429, "draft_limit_reached",
                       "Draft limit reached for this ticket (10 per hour). You can still write the reply manually.")

    ctx = await build_context(db, ticket)
    return await draft_response(client, ctx, ticket_id=ticket["_id"])


# ---------------------------------------------------------------- errors

def ai_http_error(e: AIError, fallback: str = "You can still write the reply manually.") -> AppError:
    """AIError -> consistent API error. Messages are safe; detail (internal) is never exposed."""
    message = e.message if "manually" in e.message else f"{e.message} {fallback}"
    headers = {"Retry-After": str(e.retry_after)} if e.retry_after else None
    return AppError(e.http_status, e.code, message, headers=headers)