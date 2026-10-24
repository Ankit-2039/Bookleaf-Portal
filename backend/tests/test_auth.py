import jwt
from bson import ObjectId
from fastapi import Depends

from app.api.deps import CurrentUser, require_admin, require_author
from app.core.security import create_access_token
from tests.conftest import TEST_PASSWORD
from app.main import app


# Test-only routes to exercise the role dependencies (real admin routes arrive in Step 5)
@app.get("/_test/admin-only")
async def _admin_only(user: CurrentUser = Depends(require_admin)):
    return {"ok": True}


@app.get("/_test/author-only")
async def _author_only(user: CurrentUser = Depends(require_author)):
    return {"ok": True}


def login(client, email, password=TEST_PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_login_success_author(client):
    r = login(client, "author@test.dev")
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "author"
    assert "password" not in str(body).lower()


def test_login_email_is_case_insensitive(client):
    assert login(client, "  AUTHOR@test.dev ").status_code == 200


def test_login_wrong_password(client):
    r = login(client, "author@test.dev", "wrong-password")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


def test_login_unknown_email_same_error_as_wrong_password(client):
    wrong_pw = login(client, "author@test.dev", "nope").json()
    unknown = login(client, "ghost@test.dev").json()
    assert wrong_pw == unknown  # no account enumeration


def test_login_inactive_user_rejected(client):
    assert login(client, "inactive@test.dev").status_code == 401


def test_login_validation_error_format(client):
    r = client.post("/api/v1/auth/login", json={})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_error"
    assert {d["field"] for d in err["details"]} == {"email", "password"}


def test_me_requires_token(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_me_with_valid_token(client):
    token = login(client, "author@test.dev").json()["access_token"]
    r = client.get("/api/v1/auth/me", headers=auth(token))
    assert r.status_code == 200
    assert r.json()["email"] == "author@test.dev"


def test_me_with_garbage_token(client):
    assert client.get("/api/v1/auth/me", headers=auth("not.a.jwt")).status_code == 401


def test_me_with_expired_token(client, sync_db):
    uid = str(sync_db.users.find_one({"email": "author@test.dev"})["_id"])
    token = create_access_token(uid, "author", expires_minutes=-1)
    assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 401


def test_me_with_token_signed_by_wrong_secret(client, sync_db):
    uid = str(sync_db.users.find_one({"email": "admin@test.dev"})["_id"])
    forged = jwt.encode({"sub": uid, "role": "admin", "exp": 9999999999}, "attacker-key", algorithm="HS256")
    assert client.get("/api/v1/auth/me", headers=auth(forged)).status_code == 401


def test_token_for_nonexistent_user_rejected(client):
    token = create_access_token(str(ObjectId()), "admin")
    assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 401


def test_forged_role_claim_does_not_grant_admin(client, sync_db):
    """Token says admin, but the DB says author: the DB wins."""
    uid = str(sync_db.users.find_one({"email": "author@test.dev"})["_id"])
    token = create_access_token(uid, "admin")
    assert client.get("/_test/admin-only", headers=auth(token)).status_code == 403


def test_author_blocked_from_admin_route(client):
    token = login(client, "author@test.dev").json()["access_token"]
    r = client.get("/_test/admin-only", headers=auth(token))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_admin_allowed_on_admin_route_but_not_author_route(client):
    token = login(client, "admin@test.dev").json()["access_token"]
    assert client.get("/_test/admin-only", headers=auth(token)).status_code == 200
    assert client.get("/_test/author-only", headers=auth(token)).status_code == 403