import os

# Must happen BEFORE importing the app: env vars override .env in pydantic-settings.
os.environ["MONGODB_DB"] = "bookleaf_test"
os.environ["JWT_SECRET"] = "test-secret-not-for-production"

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from app.core.config import get_settings
from app.core.security import hash_password
from app.main import app

TEST_PASSWORD = "Passw0rd!test"


@pytest.fixture(scope="session")
def sync_db():
    s = get_settings()
    assert s.mongodb_db.endswith("_test"), "Refusing to run tests against a non-test database"
    mc = MongoClient(s.mongodb_uri, tz_aware=True, serverSelectionTimeoutMS=5000)
    mc.drop_database(s.mongodb_db)
    db = mc[s.mongodb_db]

    now = datetime.now(timezone.utc)
    pw = hash_password(TEST_PASSWORD)
    db.users.insert_many([
        {"email": "author@test.dev", "name": "Test Author", "role": "author",
         "password_hash": pw, "is_active": True, "created_at": now},
        {"email": "admin@test.dev", "name": "Test Admin", "role": "admin",
         "password_hash": pw, "is_active": True, "created_at": now},
        {"email": "inactive@test.dev", "name": "Inactive", "role": "author",
         "password_hash": pw, "is_active": False, "created_at": now},
    ])
    yield db
    mc.drop_database(s.mongodb_db)
    mc.close()


@pytest.fixture(scope="session")
def client(sync_db):
    with TestClient(app) as c:  # runs the app lifespan (connects, creates indexes)
        yield c