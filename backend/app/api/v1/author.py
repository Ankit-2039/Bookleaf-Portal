from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, get_author_profile, require_author
from app.db.mongo import get_db
from app.models.enums import TicketStatus
from app.schemas.books import BookOut
from app.schemas.common import Page
from app.schemas.dashboard import AuthorDashboard
from app.schemas.tickets import AuthorTicketDetail, AuthorTicketListItem, TicketCreate
from app.services import books as book_svc
from app.services import tickets as ticket_svc
from fastapi import BackgroundTasks
from app.services import ai_tickets as ai_svc
from app.realtime import events

# Every route below requires an authenticated AUTHOR (require_author is applied via get_author_profile).
router = APIRouter(prefix="/author", tags=["author"])


@router.get("/dashboard", response_model=AuthorDashboard)
async def dashboard(author: dict = Depends(get_author_profile), db=Depends(get_db)):
    return await book_svc.author_dashboard(db, author)


@router.get("/books", response_model=list[BookOut])
async def list_books(
    q: str | None = Query(None, max_length=100, description="Search title, ISBN or genre"),
    published: bool | None = Query(None, description="true = live books, false = in production"),
    sort: Literal["title", "publication_date", "royalty_pending"] = "title",
    order: Literal["asc", "desc"] = "asc",
    author: dict = Depends(get_author_profile),
    db=Depends(get_db),
):
    return await book_svc.list_author_books(db, author, q, published, sort, order)


@router.get("/books/{book_id}", response_model=BookOut)
async def get_book(book_id: str, author: dict = Depends(get_author_profile), db=Depends(get_db)):
    return book_svc.book_to_out(await book_svc.get_author_book(db, author, book_id))


@router.post("/tickets", response_model=AuthorTicketDetail, status_code=201)
async def create_ticket(
    body: TicketCreate,
    background: BackgroundTasks,
    user: CurrentUser = Depends(require_author),
    author: dict = Depends(get_author_profile),
    db=Depends(get_db),
):
    ticket, book = await ticket_svc.create_ticket(db, author, body)
    await events.after_created(ticket)  # admins see it in the queue immediately
    background.add_task(ai_svc.triage_in_background, ticket["_id"])
    return ticket_svc.to_author_detail(ticket, book, [], user)


@router.get("/tickets", response_model=Page[AuthorTicketListItem])
async def list_tickets(
    status: TicketStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    author: dict = Depends(get_author_profile),
    db=Depends(get_db),
):
    items, total = await ticket_svc.list_author_tickets(db, author, status, page, page_size)
    return Page[AuthorTicketListItem](items=items, total=total, page=page, page_size=page_size)


@router.get("/tickets/{ticket_number}", response_model=AuthorTicketDetail)
async def get_ticket(
    ticket_number: int,
    user: CurrentUser = Depends(require_author),
    author: dict = Depends(get_author_profile),
    db=Depends(get_db),
):
    ticket = await ticket_svc.get_author_ticket(db, author, ticket_number)
    book = await db.books.find_one({"_id": ticket["book_id"]}, {"title": 1}) if ticket.get("book_id") else None
    messages = await ticket_svc.get_public_messages(db, ticket["_id"])
    return ticket_svc.to_author_detail(ticket, book, messages, user)