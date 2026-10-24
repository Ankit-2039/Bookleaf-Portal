import os

# Must happen BEFORE importing the app: env vars override .env in pydantic-settings.
os.environ["MONGODB_DB"] = "bookleaf_test"
os.environ["JWT_SECRET"] = "test-secret-not-for-production-use-only-32+bytes"

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from bson.decimal128 import Decimal128
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.core.config import get_settings
from app.core.security import hash_password
from app.main import app

TEST_PASSWORD = "Passw0rd!test"


def d(v) -> Decimal128:
    return Decimal128(Decimal(str(v)))


def _book(author_id, code, title, **over):
    base = {
        "author_id": author_id, "book_code": code, "title": title, "isbn": f"978-TEST-{code}",
        "genre": "Fiction", "publication_date": "2024-01-10", "status": "Published & Live",
        "mrp": d(400), "royalty_per_copy": d(40), "total_copies_sold": 25,
        "total_royalty_earned": d(1000), "royalty_paid": d(400), "royalty_pending": d(600),
        "last_royalty_payout_date": "2025-12-01", "print_partner": "In-House",
        "available_on": ["Amazon India"],
    }
    base.update(over)
    return base


@pytest.fixture(scope="session")
def sync_db():
    s = get_settings()
    assert s.mongodb_db.endswith("_test"), "Refusing to run tests against a non-test database"
    mc = MongoClient(s.mongodb_uri, tz_aware=True, serverSelectionTimeoutMS=5000)
    mc.drop_database(s.mongodb_db)
    db = mc[s.mongodb_db]

    now = datetime.now(timezone.utc)
    pw = hash_password(TEST_PASSWORD)

    def user(email, name, role, active=True):
        return {"email": email, "name": name, "role": role, "password_hash": pw,
                "is_active": active, "created_at": now}

    db.users.insert_many([
        user("author@test.dev", "Test Author", "author"),
        user("admin@test.dev", "Test Admin", "admin"),
        user("inactive@test.dev", "Inactive", "author", active=False),
        user("author2@test.dev", "Second Author", "author"),
        user("empty@test.dev", "Empty Author", "author"),
    ])

    def author(email, code):
        u = db.users.find_one({"email": email})
        return db.authors.insert_one(
            {"user_id": u["_id"], "author_code": code, "phone": None, "city": "Delhi", "joined_date": "2024-01-01"}
        ).inserted_id

    a1, a2 = author("author@test.dev", "T-AUTH1"), author("author2@test.dev", "T-AUTH2")
    author("empty@test.dev", "T-AUTH3")

    db.books.insert_many([
        _book(a1, "T-BK1", "Test Published Book"),
        _book(a1, "T-BK2", "Test Draft Book", status="In Production - Cover Design",
              publication_date=None, mrp=None, royalty_per_copy=None, total_copies_sold=0,
              total_royalty_earned=d(0), royalty_paid=d(0), royalty_pending=d(0),
              last_royalty_payout_date=None, print_partner=None, available_on=[]),
        _book(a2, "T-BK3", "Other Authors Book"),
    ])
    yield db
    mc.drop_database(s.mongodb_db)
    mc.close()


@pytest.fixture(scope="session")
def client(sync_db):
    with TestClient(app) as c:  # runs the app lifespan (connects, creates indexes)
        yield c


def _headers(client, email):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def author_h(client):
    return _headers(client, "author@test.dev")


@pytest.fixture(scope="session")
def author2_h(client):
    return _headers(client, "author2@test.dev")


@pytest.fixture(scope="session")
def empty_h(client):
    return _headers(client, "empty@test.dev")


@pytest.fixture(scope="session")
def admin_h(client):
    return _headers(client, "admin@test.dev")