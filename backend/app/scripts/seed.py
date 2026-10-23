"""Idempotent seed: python -m app.scripts.seed  (run from backend/)."""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from pymongo import ReturnDocument

from app.core.config import get_settings
from app.core.security import hash_password
from app.db import mongo
from app.db.money import to_d128
from app.models.enums import UserRole

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "bookleaf_sample_data.json"

ADMINS = [
    {"email": "admin@bookleaf.test", "name": "Ops Admin"},
    {"email": "support@bookleaf.test", "name": "Support Lead"},
]


def check_integrity(b: dict) -> list[str]:
    """Verify the dataset's own numbers agree; report, never silently 'fix'."""
    issues = []
    rpc, sold = b.get("author_royalty_per_copy"), b.get("total_copies_sold", 0)
    if rpc is not None and rpc * sold != b["total_royalty_earned"]:
        issues.append(f"{b['book_id']}: copies*rate != earned")
    if b["royalty_paid"] + b["royalty_pending"] != b["total_royalty_earned"]:
        issues.append(f"{b['book_id']}: paid + pending != earned")
    return issues


async def upsert_user(db, email, name, role, password, now):
    return await db.users.find_one_and_update(
        {"email": email.lower()},
        {
            "$set": {"name": name, "role": role.value, "is_active": True},
            # Only on first creation: reruns never reset an existing password
            "$setOnInsert": {"password_hash": hash_password(password), "created_at": now},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )


async def seed() -> None:
    s = get_settings()
    if not s.seed_author_password or not s.seed_admin_password:
        raise SystemExit("Set SEED_AUTHOR_PASSWORD and SEED_ADMIN_PASSWORD in .env first.")

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    await mongo.connect()
    db = mongo.get_db()
    await mongo.ensure_indexes(db)
    now = datetime.now(timezone.utc)
    issues: list[str] = []

    for adm in ADMINS:
        await upsert_user(db, adm["email"], adm["name"], UserRole.ADMIN, s.seed_admin_password, now)

    for a in data["authors"]:
        user = await upsert_user(db, a["email"], a["name"], UserRole.AUTHOR, s.seed_author_password, now)
        author = await db.authors.find_one_and_update(
            {"author_code": a["author_id"]},
            {"$set": {
                "user_id": user["_id"],
                "phone": a.get("phone"),
                "city": a.get("city"),
                "joined_date": a.get("joined_date"),
            }},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        for b in a["books"]:
            issues += check_integrity(b)
            await db.books.update_one(
                {"book_code": b["book_id"]},
                {"$set": {
                    "author_id": author["_id"],
                    "title": b["title"],
                    "isbn": b.get("isbn"),
                    "genre": b.get("genre"),
                    "publication_date": b.get("publication_date"),
                    "status": b["status"],
                    "mrp": to_d128(b.get("mrp")),
                    "royalty_per_copy": to_d128(b.get("author_royalty_per_copy")),
                    "total_copies_sold": b.get("total_copies_sold", 0),
                    "total_royalty_earned": to_d128(b.get("total_royalty_earned", 0)),
                    "royalty_paid": to_d128(b.get("royalty_paid", 0)),
                    "royalty_pending": to_d128(b.get("royalty_pending", 0)),
                    "last_royalty_payout_date": b.get("last_royalty_payout_date"),
                    "print_partner": b.get("print_partner"),
                    "available_on": b.get("available_on", []),
                }},
                upsert=True,
            )

    # Ticket number counter (first ticket will be 1001); never reset on rerun
    await db.counters.update_one({"_id": "ticket"}, {"$setOnInsert": {"seq": 1000}}, upsert=True)

    print(
        f"users={await db.users.count_documents({})} "
        f"authors={await db.authors.count_documents({})} "
        f"books={await db.books.count_documents({})}"
    )
    print("integrity issues:", issues or "none")
    await mongo.close()


if __name__ == "__main__":
    asyncio.run(seed())