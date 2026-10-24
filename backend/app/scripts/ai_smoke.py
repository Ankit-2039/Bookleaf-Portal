"""Live check against your real LLM key: python -m app.scripts.ai_smoke  (run from backend/)."""
import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal

from openai import AsyncOpenAI

from app.ai.client import AIClient
from app.ai.context import BookFacts, TicketContext
from app.ai.drafting import draft_response
from app.ai.errors import AIError
from app.ai.provider import UnconfiguredProvider, build_provider
from app.ai.triage import triage_ticket
from app.core.config import get_settings
from app.models.enums import TicketCategory, TicketPriority

# Figures below come from the supplied sample dataset (BK005 and BK001).
NEVER_PAID = BookFacts(
    title="Between Two Temples", isbn="978-93-5XXXX-05-9", status="Published & Live",
    publication_date=date(2024, 7, 5), mrp=Decimal("425"), copies_sold=67,
    royalty_earned=Decimal("2546"), royalty_paid=Decimal("0"), royalty_pending=Decimal("2546"),
    last_payout_date=None, print_partner="Epitome Books", available_on=["Amazon India", "BookLeaf Store"],
)
GANGES = BookFacts(
    title="Whispers of the Ganges", isbn="978-93-5XXXX-01-1", status="Published & Live",
    publication_date=date(2023, 6, 20), mrp=Decimal("399"), copies_sold=342,
    royalty_earned=Decimal("11970"), royalty_paid=Decimal("8400"), royalty_pending=Decimal("3570"),
    last_payout_date=date(2025, 10, 15), print_partner="In-House",
    available_on=["Amazon India", "Flipkart", "BookLeaf Store"],
)


def ctx(subject, description, book, name="Author", category=TicketCategory.GENERAL, priority=TicketPriority.MEDIUM, total=None):
    return TicketContext(
        ticket_number=1001, subject=subject, description=description, status="Open",
        category=category, priority=priority, created_at=datetime.now(timezone.utc),
        author_first_name=name, book=book, today=date.today(), author_total_pending=total,
    )


SAMPLES = [
    ("expect Royalty & Payments / High",
     ctx("No royalty received", "My book has been live for over a year and I have never received a single royalty payment. What is going on?", NEVER_PAID)),
    ("expect ISBN & Metadata Issues / High",
     ctx("Wrong ISBN on Amazon", "My book is showing a different ISBN on Amazon than what is printed on the physical copy.", GANGES)),
    ("expect General Inquiry / Low",
     ctx("Update my author bio", "Can I update the author bio on my Amazon page? Not urgent.", None)),
]


async def main() -> None:
    s = get_settings()
    provider = build_provider(s)
    if isinstance(provider, UnconfiguredProvider):
        raise SystemExit("LLM_API_KEY is not set in backend/.env")

    try:
        models = await AsyncOpenAI(api_key=s.llm_api_key, base_url=s.llm_base_url, timeout=15).models.list()
        ids = sorted(m.id for m in models.data)
        print(f"Model '{s.llm_model}' available to this key: {s.llm_model in ids}")
        if s.llm_model not in ids:
            print("Models your key can use:", ids)
    except Exception as e:
        print("Could not list models:", type(e).__name__)

    async def sink(row: dict) -> None:
        print(f"   [usage] {row['purpose']} {row['status']} {row['latency_ms']}ms "
              f"in={row['input_tokens']} out={row['output_tokens']} err={row['error_code']}")

    client = AIClient(provider, usage_sink=sink)

    for label, c in SAMPLES:
        print(f"\nTRIAGE ({label})")
        try:
            r = await triage_ticket(client, c)
            print(f"   -> {r.category.value} / {r.priority.value} (confidence {r.confidence:.2f})\n   {r.rationale}")
        except AIError as e:
            print(f"   FAILED: {e.code} - {e.message} [{e.detail}]")

    print("\nDRAFT (royalty ticket for a book that has never been paid)")
    c = ctx("No royalty received", SAMPLES[0][1].description, NEVER_PAID, name="Ananya",
            category=TicketCategory.ROYALTY, priority=TicketPriority.HIGH, total=Decimal("2546"))
    try:
        out = await draft_response(client, c)
        print(out.draft)
        print("\nVerify before sending:", out.verify_before_sending)
        print("Warnings:", out.warnings or "none")
    except AIError as e:
        print(f"   FAILED: {e.code} - {e.message} [{e.detail}]")


if __name__ == "__main__":
    asyncio.run(main())