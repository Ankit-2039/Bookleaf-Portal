import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.ai.client import AIClient
from app.ai.context import TicketContext
from app.ai.knowledge_base import PAYOUT_THRESHOLD_INR
from app.ai.prompts import build_draft_system, build_draft_user
from app.ai.schemas import DraftResult
from app.ai.structured import generate_validated

_AMOUNT = re.compile(r"(?:₹|Rs\.?|INR)\s*([0-9][0-9,]*(?:\.[0-9]+)?)", re.IGNORECASE)
_PLACEHOLDER = re.compile(r"\[[^\]\n]{2,60}\]|\{\{[^}]*\}\}")
_COMPLETED = re.compile(
    r"\b(?:has|have|had)\s+(?:already\s+)?been\s+"
    r"(?:verified|approved|confirmed|triggered|re-?printed|shipped|dispatched|processed|initiated|escalated|resolved|fixed|corrected|credited)\b",
    re.IGNORECASE,
)
_PROMISES_PAYMENT = re.compile(
    r"\b(?:will|we'll|we\s+will|are\s+going\s+to)\s+(?:\w+\s+){0,2}?"
    r"(?:release|issue|send|process|trigger|credit|pay)\b[^.]{0,40}\b(?:payout|payment|royalt\w*)\b",
    re.IGNORECASE,
)
_MODAL_BEFORE = re.compile(r"\b(?:should|would|could|might|must|may|ought\s+to)\s+$", re.IGNORECASE)


@dataclass
class DraftOutcome:
    draft: str
    verify_before_sending: list[str]
    warnings: list[str]
    model: str


def _allowed_amounts(ctx: TicketContext) -> set[Decimal]:
    allowed = {Decimal(PAYOUT_THRESHOLD_INR)}
    if ctx.book:
        for v in (ctx.book.mrp, ctx.book.royalty_earned, ctx.book.royalty_paid, ctx.book.royalty_pending):
            if v is not None:
                allowed.add(Decimal(v))
    if ctx.author_total_pending is not None:
        allowed.add(Decimal(ctx.author_total_pending))
    return allowed


def check_draft(draft: str, ctx: TicketContext) -> list[str]:
    """Deterministic guardrails. They WARN the admin; they never block or silently edit the draft."""
    warnings: list[str] = []
    allowed = _allowed_amounts(ctx)
    for raw in dict.fromkeys(m.group(1).rstrip(",") for m in _AMOUNT.finditer(draft)):
        try:
            value = Decimal(raw.replace(",", ""))
        except InvalidOperation:
            continue
        if value not in allowed:
            warnings.append(f"Draft mentions ₹{raw}, which is not in this ticket's system data. Verify or remove it.")
    if _PLACEHOLDER.search(draft):
        warnings.append("Draft contains a placeholder such as [Name]. Replace it before sending.")
    claims = [m for m in _COMPLETED.finditer(draft) if not _MODAL_BEFORE.search(draft[max(0, m.start() - 15):m.start()])]
    for m in claims[:3]:
        warnings.append(f"Draft says \"{m.group(0)}\", but the system has no record of that action. Confirm or reword.")
    if _PROMISES_PAYMENT.search(draft) or re.search(r"upcoming payment|payment confirmation", draft, re.IGNORECASE):
        warnings.append("Draft promises a payout. Only send this if finance has confirmed it.")
    return warnings


def _clean(text: str) -> str:
    return re.sub(r"\*\*|__", "", text).strip()  # plain text only


async def draft_response(client: AIClient, ctx: TicketContext, *, ticket_id=None) -> DraftOutcome:
    result = await generate_validated(
        client,
        purpose="draft",
        ticket_id=ticket_id,
        system=build_draft_system(ctx.category, all_sections=not ctx.category_reliable),
        user=build_draft_user(ctx),
        schema=DraftResult,
        max_tokens=2500,
        reasoning_effort="medium",
        temperature=0.4,
    )
    draft = _clean(result.draft)
    return DraftOutcome(
        draft=draft,
        verify_before_sending=result.verify_before_sending,
        warnings=check_draft(draft, ctx),
        model=client.provider.model,
    )