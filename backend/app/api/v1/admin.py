from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import CurrentUser, require_admin
from app.db.mongo import get_db
from app.models.enums import TicketCategory, TicketPriority, TicketStatus
from app.schemas.admin import (
    AdminMessageOut,
    AdminMetrics,
    AdminTicketDetail,
    AdminTicketListItem,
    NoteCreate,
    ReplyCreate,
    TicketPatch,
    UserRef,
)
from app.schemas.common import Page
from app.services import admin_tickets as svc

# Router-level dependency: every route here requires an authenticated ADMIN.
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/metrics", response_model=AdminMetrics)
async def get_metrics(admin: CurrentUser = Depends(require_admin), db=Depends(get_db)):
    return await svc.metrics(db, admin)


@router.get("/admins", response_model=list[UserRef])
async def list_admins(db=Depends(get_db)):
    """For the 'assign to' dropdown."""
    return await svc.list_admins(db)


@router.get("/tickets", response_model=Page[AdminTicketListItem])
async def list_tickets(
    status: list[TicketStatus] | None = Query(None),
    category: list[TicketCategory] | None = Query(None),
    priority: list[TicketPriority] | None = Query(None),
    assignee: str | None = Query(None, max_length=24, description="'me', 'unassigned' or an admin id"),
    date_from: date | None = Query(None, description="Created on or after (UTC)"),
    date_to: date | None = Query(None, description="Created on or before (UTC)"),
    q: str | None = Query(None, max_length=100, description="Ticket id, subject, author name or email"),
    sort: Literal["urgency", "newest", "oldest", "updated"] = "urgency",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    admin: CurrentUser = Depends(require_admin),
    db=Depends(get_db),
):
    qq = svc.QueueQuery(status, category, priority, assignee, date_from, date_to, q, sort, page, page_size)
    items, total = await svc.list_tickets(db, admin, qq)
    return Page[AdminTicketListItem](items=items, total=total, page=page, page_size=page_size)


@router.get("/tickets/{ticket_number}", response_model=AdminTicketDetail)
async def get_ticket(ticket_number: int, db=Depends(get_db)):
    return await svc.build_detail(db, await svc.get_ticket(db, ticket_number))


@router.patch("/tickets/{ticket_number}", response_model=AdminTicketDetail)
async def update_ticket(
    ticket_number: int, body: TicketPatch, admin: CurrentUser = Depends(require_admin), db=Depends(get_db)
):
    ticket = await svc.get_ticket(db, ticket_number)
    updated = await svc.patch_ticket(db, admin, ticket, body)
    return await svc.build_detail(db, updated)


@router.post("/tickets/{ticket_number}/notes", response_model=AdminMessageOut, status_code=201)
async def add_note(
    ticket_number: int, body: NoteCreate, admin: CurrentUser = Depends(require_admin), db=Depends(get_db)
):
    ticket = await svc.get_ticket(db, ticket_number)
    return await svc.message_out(db, await svc.add_note(db, admin, ticket, body))


@router.post("/tickets/{ticket_number}/replies", response_model=AdminMessageOut, status_code=201)
async def send_reply(
    ticket_number: int,
    body: ReplyCreate,
    response: Response,
    admin: CurrentUser = Depends(require_admin),
    db=Depends(get_db),
):
    ticket = await svc.get_ticket(db, ticket_number)
    message, created = await svc.add_reply(db, admin, ticket, body)
    if not created:
        response.status_code = 200  # idempotent retry: same message returned, nothing duplicated
    # Step 8 hooks in here: after persisting a NEW public reply, push it to the author's WebSocket.
    return await svc.message_out(db, message)