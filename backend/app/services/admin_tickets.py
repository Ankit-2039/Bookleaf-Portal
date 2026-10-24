import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError

from app.api.deps import CurrentUser
from app.core.clock import utcnow
from app.core.errors import AppError
from app.models.enums import PRIORITY_RANK, MessageKind, TicketStatus
from app.schemas.admin import (
    AdminMessageOut,
    AdminMetrics,
    AdminTicketDetail,
    AdminTicketListItem,
    AiTriage,
    AuditOut,
    AuthorRef,
    NoteCreate,
    ReplyCreate,
    TicketPatch,
    UserRef,
)
from app.schemas.tickets import BookRef
from app.services.books import book_to_out
from app.services.tickets import display_id

S = TicketStatus
ACTIVE = [S.OPEN.value, S.IN_PROGRESS.value]

ALLOWED_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    S.OPEN: {S.IN_PROGRESS, S.RESOLVED, S.CLOSED},
    S.IN_PROGRESS: {S.OPEN, S.RESOLVED, S.CLOSED},
    S.RESOLVED: {S.IN_PROGRESS, S.CLOSED},  # reopen allowed
    S.CLOSED: set(),                        # terminal
}

# "active" is computed in the pipeline: 0 for unresolved, 1 for resolved/closed.
SORTS = {
    "urgency": [("active", 1), ("priority_rank", 1), ("created_at", 1)],
    "newest": [("created_at", -1)],
    "oldest": [("created_at", 1)],
    "updated": [("updated_at", -1)],
}


@dataclass
class QueueQuery:
    statuses: list | None = None
    categories: list | None = None
    priorities: list | None = None
    assignee: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    q: str | None = None
    sort: str = "urgency"
    page: int = 1
    page_size: int = 25


# ---------------------------------------------------------------- lookups

async def get_ticket(db, ticket_number: int) -> dict:
    t = await db.tickets.find_one({"ticket_number": ticket_number})
    if t is None:
        raise AppError(404, "not_found", "Ticket not found.")
    return t


async def _users_by_id(db, ids) -> dict:
    ids = list(ids)
    if not ids:
        return {}
    return {u["_id"]: u async for u in db.users.find({"_id": {"$in": ids}}, {"name": 1, "email": 1, "role": 1})}


def _user_ref(users: dict, oid) -> UserRef:
    u = users.get(oid)
    return UserRef(id=str(oid), name=u["name"] if u else "Unknown")


async def list_admins(db) -> list[UserRef]:
    cursor = db.users.find({"role": "admin", "is_active": True}).sort("name", 1)
    return [UserRef(id=str(u["_id"]), name=u["name"]) async for u in cursor]


# ---------------------------------------------------------------- queue

def _parse_oid_422(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise AppError(422, "invalid_assignee", "Assignee must be 'me', 'unassigned' or an admin id.")


async def _search_clause(db, q: str) -> dict:
    q = q.strip()
    ors = []
    m = re.fullmatch(r"(?i)(?:tkt-?)?(\d{1,9})", q)
    if m:
        ors.append({"ticket_number": int(m.group(1))})
    rx = {"$regex": re.escape(q), "$options": "i"}  # escaped: user input is never a regex
    ors.append({"subject": rx})
    users = await db.users.find({"role": "author", "$or": [{"name": rx}, {"email": rx}]}, {"_id": 1}).to_list()
    if users:
        authors = await db.authors.find({"user_id": {"$in": [u["_id"] for u in users]}}, {"_id": 1}).to_list()
        if authors:
            ors.append({"author_id": {"$in": [a["_id"] for a in authors]}})
    return {"$or": ors}


async def _build_filter(db, admin: CurrentUser, qq: QueueQuery) -> dict:
    flt: dict = {}
    if qq.statuses:
        flt["status"] = {"$in": [s.value for s in qq.statuses]}
    if qq.categories:
        flt["category"] = {"$in": [c.value for c in qq.categories]}
    if qq.priorities:
        flt["priority"] = {"$in": [p.value for p in qq.priorities]}
    if qq.assignee == "me":
        flt["assignee_id"] = admin.oid
    elif qq.assignee == "unassigned":
        flt["assignee_id"] = None
    elif qq.assignee:
        flt["assignee_id"] = _parse_oid_422(qq.assignee)

    created = {}
    if qq.date_from:
        created["$gte"] = datetime.combine(qq.date_from, time.min, tzinfo=timezone.utc)
    if qq.date_to:  # inclusive of the whole end day
        created["$lt"] = datetime.combine(qq.date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
    if created:
        flt["created_at"] = created

    if qq.q and qq.q.strip():
        flt.update(await _search_clause(db, qq.q))
    return flt


async def _run_queue(db, flt: dict, sort: str, skip: int, limit: int) -> list[dict]:
    spec = SORTS[sort]
    tie_break = spec[-1][1]
    pipeline = [
        {"$match": flt},
        {"$addFields": {"active": {"$cond": [{"$in": ["$status", ACTIVE]}, 0, 1]}}},
        {"$sort": {**{k: v for k, v in spec}, "_id": tie_break}},
        {"$skip": skip},
        {"$limit": limit},
    ]
    cursor = await db.tickets.aggregate(pipeline)
    return await cursor.to_list()


async def hydrate_list(db, tickets: list[dict]) -> list[AdminTicketListItem]:
    """Batch-load authors, books and assignees: 3 queries total, not 3 per ticket."""
    if not tickets:
        return []
    authors = {a["_id"]: a async for a in db.authors.find({"_id": {"$in": list({t["author_id"] for t in tickets})}})}
    book_ids = list({t["book_id"] for t in tickets if t.get("book_id")})
    books = {b["_id"]: b async for b in db.books.find({"_id": {"$in": book_ids}}, {"title": 1})} if book_ids else {}
    user_ids = {a["user_id"] for a in authors.values()} | {t["assignee_id"] for t in tickets if t.get("assignee_id")}
    users = await _users_by_id(db, user_ids)

    items = []
    for t in tickets:
        a = authors[t["author_id"]]
        au = users[a["user_id"]]
        book = books.get(t.get("book_id"))
        items.append(AdminTicketListItem(
            ticket_number=t["ticket_number"],
            display_id=display_id(t["ticket_number"]),
            subject=t["subject"],
            author=AuthorRef(id=str(a["_id"]), author_code=a["author_code"], name=au["name"],
                             email=au["email"], city=a.get("city")),
            book=BookRef(id=str(book["_id"]), title=book["title"]) if book else None,
            category=t["category"],
            priority=t["priority"],
            status=t["status"],
            assignee=_user_ref(users, t["assignee_id"]) if t.get("assignee_id") else None,
            classification_status=t.get("classification_status", "pending"),
            category_overridden=t.get("category_overridden", False),
            priority_overridden=t.get("priority_overridden", False),
            created_at=t["created_at"],
            updated_at=t["updated_at"],
        ))
    return items


async def list_tickets(db, admin: CurrentUser, qq: QueueQuery):
    if qq.date_from and qq.date_to and qq.date_from > qq.date_to:
        raise AppError(422, "invalid_date_range", "date_from must not be after date_to.")
    flt = await _build_filter(db, admin, qq)
    total = await db.tickets.count_documents(flt)
    tickets = await _run_queue(db, flt, qq.sort, (qq.page - 1) * qq.page_size, qq.page_size)
    return await hydrate_list(db, tickets), total


# ---------------------------------------------------------------- detail

def _message_out(m: dict, users: dict) -> AdminMessageOut:
    u = users.get(m["sender_id"])
    return AdminMessageOut(
        id=str(m["_id"]),
        kind=m["kind"],
        body=m["body"],
        created_at=m["created_at"],
        sender=_user_ref(users, m["sender_id"]),
        sender_role=u["role"] if u else "unknown",
        ai_drafted=m.get("ai_drafted", False),
    )


async def message_out(db, m: dict) -> AdminMessageOut:
    return _message_out(m, await _users_by_id(db, [m["sender_id"]]))


async def build_detail(db, t: dict) -> AdminTicketDetail:
    [item] = await hydrate_list(db, [t])
    book = await db.books.find_one({"_id": t["book_id"]}) if t.get("book_id") else None
    msgs = await db.ticket_messages.find({"ticket_id": t["_id"]}).sort([("created_at", 1), ("_id", 1)]).to_list()
    events = await db.audit_events.find({"ticket_id": t["_id"]}).sort([("created_at", 1), ("_id", 1)]).to_list()
    users = await _users_by_id(db, {m["sender_id"] for m in msgs} | {e["actor_id"] for e in events if e.get("actor_id")})

    return AdminTicketDetail(
        **item.model_dump(),
        description=t["description"],
        resolved_at=t.get("resolved_at"),
        book_detail=book_to_out(book) if book else None,
        ai=AiTriage(
            ai_category=t.get("ai_category"),
            ai_priority=t.get("ai_priority"),
            ai_confidence=t.get("ai_confidence"),
            ai_rationale=t.get("ai_rationale"),
            classified_at=t.get("classified_at"),
        ),
        messages=[_message_out(m, users) for m in msgs],
        audit=[
            AuditOut(
                id=str(e["_id"]), action=e["action"], old_value=e.get("old_value"), new_value=e.get("new_value"),
                actor=_user_ref(users, e["actor_id"]) if e.get("actor_id") else None, created_at=e["created_at"],
            )
            for e in events
        ],
    )


# ---------------------------------------------------------------- updates

async def _audit(db, ticket_oid, actor_oid, events: list[tuple], now) -> None:
    if events:
        await db.audit_events.insert_many([
            {"ticket_id": ticket_oid, "actor_id": actor_oid, "action": a, "old_value": o, "new_value": n,
             "created_at": now}
            for a, o, n in events
        ])


def _status_sets(ticket: dict, new: TicketStatus, now) -> dict:
    sets = {"status": new.value}
    if new == S.RESOLVED:
        sets["resolved_at"] = now
    elif new == S.CLOSED:
        if not ticket.get("resolved_at"):
            sets["resolved_at"] = now
    else:  # reopened
        sets["resolved_at"] = None
    return sets


def _check_transition(cur: TicketStatus, new: TicketStatus) -> None:
    if new != cur and new not in ALLOWED_TRANSITIONS[cur]:
        raise AppError(409, "invalid_status_transition", f"Cannot move a ticket from {cur.value} to {new.value}.")


async def _resolve_assignee(db, admin: CurrentUser, value: str | None):
    if value is None:
        return None
    if value == "me":
        return admin.oid
    oid = _parse_oid_422(value)
    if await db.users.find_one({"_id": oid, "role": "admin", "is_active": True}) is None:
        raise AppError(422, "invalid_assignee", "Assignee must be an active admin.")
    return oid


async def _name(db, oid) -> str | None:
    if oid is None:
        return None
    u = await db.users.find_one({"_id": oid}, {"name": 1})
    return u["name"] if u else None


async def patch_ticket(db, admin: CurrentUser, ticket: dict, patch: TicketPatch) -> dict:
    now = utcnow()
    fields = patch.model_fields_set
    sets: dict = {}
    audits: list[tuple] = []

    if "status" in fields and patch.status.value != ticket["status"]:
        cur = TicketStatus(ticket["status"])
        _check_transition(cur, patch.status)
        sets.update(_status_sets(ticket, patch.status, now))
        audits.append(("status_changed", cur.value, patch.status.value))

    if "category" in fields:
        new = patch.category.value
        # Confirming the AI's value also counts: it locks the field against later AI writes.
        if new != ticket["category"] or not ticket.get("category_overridden"):
            sets.update({"category": new, "category_overridden": True})
            audits.append(("category_overridden", ticket["category"], new))

    if "priority" in fields:
        new = patch.priority
        if new.value != ticket["priority"] or not ticket.get("priority_overridden"):
            sets.update({"priority": new.value, "priority_rank": PRIORITY_RANK[new], "priority_overridden": True})
            audits.append(("priority_overridden", ticket["priority"], new.value))

    if "assignee_id" in fields:
        new_oid = await _resolve_assignee(db, admin, patch.assignee_id)
        if new_oid != ticket.get("assignee_id"):
            sets["assignee_id"] = new_oid
            audits.append(("assigned", await _name(db, ticket.get("assignee_id")), await _name(db, new_oid)))

    if not sets:
        return ticket  # nothing changed

    sets["updated_at"] = now
    # Optimistic concurrency: only apply if the status is still what we validated against.
    result = await db.tickets.update_one({"_id": ticket["_id"], "status": ticket["status"]}, {"$set": sets})
    if result.matched_count == 0:
        raise AppError(409, "ticket_modified", "This ticket was changed by someone else. Refresh and try again.")
    await _audit(db, ticket["_id"], admin.oid, audits, now)
    return await db.tickets.find_one({"_id": ticket["_id"]})


async def add_note(db, admin: CurrentUser, ticket: dict, body: NoteCreate) -> dict:
    now = utcnow()
    doc = {"ticket_id": ticket["_id"], "sender_id": admin.oid, "kind": MessageKind.INTERNAL.value,
           "body": body.body, "ai_drafted": False, "created_at": now}
    doc["_id"] = (await db.ticket_messages.insert_one(doc)).inserted_id
    # Deliberately does NOT touch tickets.updated_at: authors see that timestamp.
    await _audit(db, ticket["_id"], admin.oid, [("note_added", None, None)], now)
    return doc


async def add_reply(db, admin: CurrentUser, ticket: dict, body: ReplyCreate) -> tuple[dict, bool]:
    """Returns (message, created). created=False means an identical retry was detected."""
    cur = TicketStatus(ticket["status"])
    if cur == S.CLOSED:
        raise AppError(409, "ticket_closed", "Closed tickets cannot receive replies.")
    if body.set_status:
        _check_transition(cur, body.set_status)  # validate BEFORE storing anything
    target = body.set_status or (S.IN_PROGRESS if cur == S.OPEN else cur)

    now = utcnow()
    doc = {"ticket_id": ticket["_id"], "sender_id": admin.oid, "kind": MessageKind.PUBLIC.value,
           "body": body.body, "client_msg_id": body.client_msg_id, "ai_drafted": body.from_ai_draft,
           "created_at": now}
    try:
        doc["_id"] = (await db.ticket_messages.insert_one(doc)).inserted_id  # message is persisted first
    except DuplicateKeyError:
        existing = await db.ticket_messages.find_one(
            {"ticket_id": ticket["_id"], "client_msg_id": body.client_msg_id}
        )
        return existing, False

    sets: dict = {"updated_at": now}
    audits: list[tuple] = [("reply_sent", None, None)]
    if target != cur:
        sets.update(_status_sets(ticket, target, now))
        audits.append(("status_changed", cur.value, target.value))
    if ticket.get("assignee_id") is None:
        sets["assignee_id"] = admin.oid
        audits.append(("assigned", None, admin.name))
    await db.tickets.update_one({"_id": ticket["_id"]}, {"$set": sets})
    await _audit(db, ticket["_id"], admin.oid, audits, now)
    return doc, True


# ---------------------------------------------------------------- metrics

async def metrics(db, admin: CurrentUser) -> AdminMetrics:
    cursor = await db.tickets.aggregate([{"$facet": {
        "by_status": [{"$group": {"_id": "$status", "n": {"$sum": 1}}}],
        "urgent": [{"$match": {"status": {"$in": ACTIVE}, "priority_rank": {"$lte": 1}}}, {"$count": "n"}],
        "unassigned": [{"$match": {"status": {"$in": ACTIVE}, "assignee_id": None}}, {"$count": "n"}],
        "mine": [{"$match": {"status": {"$in": ACTIVE}, "assignee_id": admin.oid}}, {"$count": "n"}],
        "resolution": [
            {"$match": {"resolved_at": {"$ne": None}}},
            {"$group": {"_id": None, "avg_ms": {"$avg": {"$subtract": ["$resolved_at", "$created_at"]}}}},
        ],
    }}])
    row = (await cursor.to_list())[0]

    by_status = {s.value: 0 for s in TicketStatus}
    for r in row["by_status"]:
        by_status[r["_id"]] = r["n"]
    count = lambda key: row[key][0]["n"] if row[key] else 0  # noqa: E731
    avg_ms = row["resolution"][0]["avg_ms"] if row["resolution"] else None

    active_filter = {"status": {"$in": ACTIVE}}
    urgent = await _run_queue(db, active_filter, "urgency", 0, 5)
    waiting = await _run_queue(db, active_filter, "oldest", 0, 5)

    return AdminMetrics(
        total_tickets=sum(by_status.values()),
        open_tickets=by_status[S.OPEN.value],
        in_progress_tickets=by_status[S.IN_PROGRESS.value],
        resolved_tickets=by_status[S.RESOLVED.value],
        closed_tickets=by_status[S.CLOSED.value],
        urgent_unresolved=count("urgent"),
        unassigned_unresolved=count("unassigned"),
        assigned_to_me=count("mine"),
        avg_resolution_hours=round(avg_ms / 3_600_000, 2) if avg_ms is not None else None,
        urgent_queue=await hydrate_list(db, urgent),
        longest_waiting=await hydrate_list(db, waiting),
    )