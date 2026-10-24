from app.ai.client import AIClient
from app.ai.context import TicketContext
from app.ai.prompts import TRIAGE_SYSTEM, build_triage_user
from app.ai.schemas import TriageResult
from app.ai.structured import generate_validated


async def triage_ticket(client: AIClient, ctx: TicketContext, *, ticket_id=None) -> TriageResult:
    """One call -> category + priority + confidence + rationale (validated)."""
    return await generate_validated(
        client,
        purpose="triage",
        ticket_id=ticket_id,
        system=TRIAGE_SYSTEM,
        user=build_triage_user(ctx),
        schema=TriageResult,
        max_tokens=1000,
        reasoning_effort="low",
        temperature=0.1,
    )