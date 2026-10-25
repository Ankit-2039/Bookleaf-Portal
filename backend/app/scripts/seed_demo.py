"""Idempotent demo tickets: python -m app.scripts.seed_demo  (run from backend/, after the main seed).
Uses the real triage code when LLM_API_KEY is set; otherwise tickets stay 'pending' and an admin can re-run AI triage."""
import asyncio
from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument

from app.ai.deps import get_ai_client
from app.ai.errors import AIError
from app.db import mongo
from app.models.enums import PRIORITY_RANK, TicketPriority
from app.services import ai_tickets

H, D = 1, 24  # hours


def _ago(hours: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)


# (key, author email, book title or None, subject, description, hours old, status, extras)
DEMO = [
    ("demo-01", "ananya.reddy@email.com", "Between Two Temples", "No royalty received",
     "My book has been live for over a year and I have never received a single royalty payment. What is going on?",
     9 * D, "Open", {}),
    ("demo-02", "rohit.kapoor@email.com", "Startup Sutra", "Wrong ISBN on Amazon",
     "The ISBN on the Amazon page is different from the one printed on the back of my physical copy.",
     3 * D, "Open", {}),
    ("demo-03", "meera.nair@email.com", "Cardamom & Chaos", "Blurry print quality on author copies",
     "My author copies arrived and the print quality is terrible. The images are blurry and the pages are misaligned.",
     26 * H, "In Progress", {"assign": "admin@bookleaf.test",
                              "reply": "Hi Meera, I'm sorry about the print quality. Could you share a few photos of the affected copies? Once we verify the defect, we will arrange a free reprint.",
                              "note": "Check with the Repro India batch for this order before approving the reprint."}),
    ("demo-04", "farhan.sheikh@email.com", "Ghazal of the Forgotten", "Update my author bio",
     "Can I update the author bio on my Amazon page? No rush.",
     5 * H, "Open", {}),
    ("demo-05", "sneha.kulkarni@email.com", "Midnight in Mysore", "Cover design status",
     "It has been three weeks and I would like to know when the cover design will be done.",
     50 * H, "Open", {}),
    ("demo-06", "priya.sharma@email.com", "Whispers of the Ganges", "Showing as Currently Unavailable",
     "My book is published but it shows Currently Unavailable on Flipkart.",
     20 * H, "Open", {}),
    ("demo-07", "diya.chatterjee@email.com", "Howrah Nights", "How is my royalty calculated?",
     "I sold 45 copies but I am not sure how my royalty is worked out. Can you explain?",
     6 * D, "Resolved", {"assign": "support@bookleaf.test",
                          "reply": "Hi Diya, royalties are 80% of the net profit per book, where net profit is the MRP minus printing cost, platform commission and shipping. I'm happy to share a line-by-line breakdown if you'd like."}),
    ("demo-08", "kavita.deshmukh@email.com", None, "Which package should I choose?",
     "What is the difference between the Standard Free and Bestseller Breakthrough packages?",
     2 * H, "Open", {}),
    ("demo-09", "vikram.joshi@email.com", "Debugging Life", "Royalty seems lower than expected",
     "I expected a higher royalty based on my sales. Can you help me understand the calculation?",
     40 * H, "Open", {}),
    ("demo-10", "arjun.malhotra@email.com", "Turban Tales", "Still no royalty after a year",
     "Turban Tales has been on sale for over a year and I have not received any royalty. I have asked before.",
     4 * D, "Open", {}),
]


async def _ticket_number(db) -> int:
    doc = await db.counters.find_one_and_update(
        {"_id": "ticket"}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER
    )
    return doc["seq"]


async def seed_demo() -> None:
    await mongo.connect()
    db = mongo.get_db()
    await mongo.ensure_indexes(db)
    await db.tickets.create_index("demo_key", unique=True, partialFilterExpression={"demo_key": {"$type": "string"}})

    created: list = []
    for key, email, book_title, subject, description, hours, status, extra in DEMO:
        if await db.tickets.find_one({"demo_key": key}):
            continue
        user = await db.users.find_one({"email": email})
        author = await db.authors.find_one({"user_id": user["_id"]}) if user else None
        if author is None:
            print(f"skip {key}: run `python -m app.scripts.seed` first ({email} not found)")
            continue
        book = await db.books.find_one({"author_id": author["_id"], "title": book_title}) if book_title else None
        if book_title and book is None:
            print(f"skip {key}: book '{book_title}' not found")
            continue

        created_at = _ago(hours)
        doc = {
            "demo_key": key,
            "ticket_number": await _ticket_number(db),
            "author_id": author["_id"],
            "book_id": book["_id"] if book else None,
            "subject": subject,
            "description": description,
            "status": "Open",
            "category": "General Inquiry",
            "priority": "Medium",
            "priority_rank": PRIORITY_RANK[TicketPriority.MEDIUM],
            "classification_status": "pending",
            "ai_category": None, "ai_priority": None, "ai_confidence": None, "ai_rationale": None,
            "classified_at": None,
            "category_overridden": False, "priority_overridden": False,
            "assignee_id": None,
            "created_at": created_at, "updated_at": created_at, "resolved_at": None,
        }
        res = await db.tickets.insert_one(doc)
        oid = res.inserted_id
        created.append(oid)

        admin = await db.users.find_one({"email": extra["assign"]}) if "assign" in extra else None
        sets: dict = {}
        if admin:
            sets["assignee_id"] = admin["_id"]
        if "reply" in extra and admin:
            replied_at = created_at + timedelta(hours=min(hours / 2, 3))
            await db.ticket_messages.insert_one({
                "ticket_id": oid, "sender_id": admin["_id"], "kind": "public", "body": extra["reply"],
                "client_msg_id": f"{key}-reply", "ai_drafted": False, "created_at": replied_at,
            })
            sets["updated_at"] = replied_at
        if "note" in extra and admin:
            await db.ticket_messages.insert_one({
                "ticket_id": oid, "sender_id": admin["_id"], "kind": "internal", "body": extra["note"],
                "client_msg_id": f"{key}-note", "ai_drafted": False,
                "created_at": created_at + timedelta(hours=min(hours / 2, 3) + 0.1),
            })
        if status != "Open":
            sets["status"] = status
        if status == "Resolved":
            sets["resolved_at"] = created_at + timedelta(hours=min(hours / 2, 20))
            sets["updated_at"] = sets["resolved_at"]
        if sets:
            await db.tickets.update_one({"_id": oid}, {"$set": sets})
        print(f"created {key}: {subject}")

    # Real triage on the new tickets (skipped cleanly when no key is configured)
    client = get_ai_client()
    for oid in created:
        try:
            await ai_tickets.run_triage(db, oid, client)
        except AIError as e:
            print(f"triage skipped for a demo ticket: {e.code}")
    print(f"done: {len(created)} demo ticket(s) created, {await db.tickets.count_documents({})} tickets in total")
    await mongo.close()


if __name__ == "__main__":
    asyncio.run(seed_demo())