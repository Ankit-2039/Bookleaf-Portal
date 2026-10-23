from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import get_settings

_client: AsyncMongoClient | None = None
_db: AsyncDatabase | None = None


async def connect() -> None:
    """Open the client and fail fast if the database is unreachable."""
    global _client, _db
    s = get_settings()
    _client = AsyncMongoClient(s.mongodb_uri, serverSelectionTimeoutMS=5000, tz_aware=True)
    _db = _client[s.mongodb_db]
    await _client.admin.command("ping")


async def close() -> None:
    if _client is not None:
        await _client.close()


def get_db() -> AsyncDatabase:
    if _db is None:
        raise RuntimeError("Database not connected")
    return _db


async def ensure_indexes(db: AsyncDatabase) -> None:
    """Idempotent: safe to run on every startup (our stand-in for schema migrations)."""
    await db.users.create_index("email", unique=True)
    await db.authors.create_index("author_code", unique=True)
    await db.authors.create_index("user_id", unique=True)
    await db.books.create_index("book_code", unique=True)
    await db.books.create_index("author_id")

    await db.tickets.create_index([("author_id", 1), ("created_at", -1)])
    # Queue ordering: status, then urgency, then oldest first
    await db.tickets.create_index([("status", 1), ("priority_rank", 1), ("created_at", 1)])
    await db.tickets.create_index("assignee_id")

    await db.ticket_messages.create_index([("ticket_id", 1), ("created_at", 1)])
    # Idempotent sends: one message per (ticket, client_msg_id), only when a key is given
    await db.ticket_messages.create_index(
        [("ticket_id", 1), ("client_msg_id", 1)],
        unique=True,
        partialFilterExpression={"client_msg_id": {"$type": "string"}},
    )
    await db.audit_events.create_index([("ticket_id", 1), ("created_at", 1)])
    await db.ai_calls.create_index([("ticket_id", 1), ("created_at", -1)])