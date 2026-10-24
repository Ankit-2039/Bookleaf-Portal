from datetime import date, datetime, timezone
from decimal import Decimal

from app.ai.context import BookFacts, TicketContext
from app.ai.provider import LLMResponse
from app.models.enums import TicketCategory, TicketPriority


class FakeProvider:
    """Plays back scripted outcomes: a string is a model reply, an Exception is raised."""
    model = "fake-model"

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls: list[dict] = []

    async def complete(self, system, user, **kwargs):
        self.calls.append({"system": system, "user": user, **kwargs})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return LLMResponse(text=outcome, model=self.model, input_tokens=120, output_tokens=40, finish_reason="stop")


def make_book(**over) -> BookFacts:
    base = dict(
        title="Whispers of the Ganges", isbn="978-93-5XXXX-01-1", status="Published & Live",
        publication_date=date(2023, 6, 20), mrp=Decimal("399"), copies_sold=342,
        royalty_earned=Decimal("11970"), royalty_paid=Decimal("8400"), royalty_pending=Decimal("3570"),
        last_payout_date=date(2025, 10, 15), print_partner="In-House",
        available_on=["Amazon India", "Flipkart", "BookLeaf Store"],
    )
    base.update(over)
    return BookFacts(**base)


def make_ctx(**over) -> TicketContext:
    base = dict(
        ticket_number=1001, subject="Royalty not received",
        description="I have not received any royalty for months. What is going on?",
        status="Open", category=TicketCategory.ROYALTY, priority=TicketPriority.HIGH,
        created_at=datetime(2026, 10, 20, tzinfo=timezone.utc), author_first_name="Priya",
        book=make_book(), today=date(2026, 10, 24), author_total_pending=Decimal("3570"), history=[],
    )
    base.update(over)
    return TicketContext(**base)