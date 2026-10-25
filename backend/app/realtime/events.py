import logging

from app.core.clock import utcnow
from app.realtime.manager import hub

logger = logging.getLogger("bookleaf.realtime")

ADMINS_CHANNEL = "admins"


def author_channel(author_oid) -> str:
    return f"author:{author_oid}"


async def _publish(channel: str, event_type: str, ticket_number: int, reason: str) -> None:
    # Events carry identifiers only: never message text, notes or personal data.
    payload = {"type": event_type, "ticket_number": ticket_number, "reason": reason, "at": utcnow().isoformat()}
    try:
        await hub.send(channel, payload)
    except Exception:  # a notification problem must never fail the request that caused it
        logger.warning("Could not publish a realtime event")


async def notify_admins(event_type: str, ticket_number: int, reason: str) -> None:
    await _publish(ADMINS_CHANNEL, event_type, ticket_number, reason)


async def notify_author(author_oid, ticket_number: int, reason: str) -> None:
    await _publish(author_channel(author_oid), "ticket.updated", ticket_number, reason)


# ---- one function per product event; routes and services call these AFTER the DB write ----

async def after_created(ticket: dict) -> None:
    await notify_admins("ticket.created", ticket["ticket_number"], "created")


async def after_reply(ticket: dict) -> None:
    await notify_admins("ticket.updated", ticket["ticket_number"], "reply")
    await notify_author(ticket["author_id"], ticket["ticket_number"], "reply")


async def after_note(ticket: dict) -> None:
    # Internal notes: admins only, never the author.
    await notify_admins("ticket.updated", ticket["ticket_number"], "note")


async def after_triage(ticket: dict) -> None:
    await notify_admins("ticket.updated", ticket["ticket_number"], "triage")
    await notify_author(ticket["author_id"], ticket["ticket_number"], "triage")


async def after_triage_failed(ticket: dict) -> None:
    await notify_admins("ticket.updated", ticket["ticket_number"], "triage_failed")


async def after_patch(before: dict, after: dict) -> None:
    if after["updated_at"] == before["updated_at"]:
        return  # nothing changed, nothing to announce
    n = after["ticket_number"]
    status_changed = after["status"] != before["status"]
    author_visible = status_changed or after["category"] != before["category"] or after["priority"] != before["priority"]

    if status_changed:
        reason = "status"
    elif author_visible:
        reason = "details"
    elif after.get("assignee_id") != before.get("assignee_id"):
        reason = "assignment"
    else:
        reason = "details"

    await notify_admins("ticket.updated", n, reason)
    if author_visible:  # authors don't see assignees, so assignment-only changes stay private
        await notify_author(after["author_id"], n, reason)