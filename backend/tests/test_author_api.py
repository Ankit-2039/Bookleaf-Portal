from datetime import datetime, timedelta, timezone

import pytest

API = "/api/v1/author"
GENERAL = {"book_id": None, "subject": "Question about my account", "description": "Please tell me how to update my bio."}


def make_ticket(client, headers, **over):
    r = client.post(f"{API}/tickets", json={**GENERAL, **over}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def book_id(sync_db, code):
    return str(sync_db.books.find_one({"book_code": code})["_id"])


# ---------- access control ----------

def test_endpoints_require_authentication(client):
    assert client.get(f"{API}/dashboard").status_code == 401
    assert client.get(f"{API}/books").status_code == 401
    assert client.get(f"{API}/tickets").status_code == 401
    assert client.post(f"{API}/tickets", json=GENERAL).status_code == 401


def test_admin_cannot_use_author_endpoints(client, admin_h):
    assert client.get(f"{API}/dashboard", headers=admin_h).status_code == 403
    assert client.get(f"{API}/books", headers=admin_h).status_code == 403


# ---------- dashboard ----------

def test_dashboard_empty_author_is_all_zeros(client, empty_h):
    d = client.get(f"{API}/dashboard", headers=empty_h).json()
    assert d["total_books"] == 0 and d["published_books"] == 0 and d["books_in_production"] == 0
    assert d["total_royalty_earned"] == 0 and d["royalty_pending"] == 0
    assert d["open_tickets"] == 0 and d["total_tickets"] == 0
    assert set(d["tickets_by_status"]) == {"Open", "In Progress", "Resolved", "Closed"}


def test_dashboard_totals_come_from_the_authors_own_books(client, author_h):
    d = client.get(f"{API}/dashboard", headers=author_h).json()
    assert d["total_books"] == 2
    assert d["published_books"] == 1
    assert d["books_in_production"] == 1
    assert d["total_royalty_earned"] == 1000
    assert d["royalty_paid"] == 400
    assert d["royalty_pending"] == 600  # the other author's book is not included


def test_dashboard_open_tickets_increments(client, author_h):
    before = client.get(f"{API}/dashboard", headers=author_h).json()["open_tickets"]
    make_ticket(client, author_h)
    after = client.get(f"{API}/dashboard", headers=author_h).json()["open_tickets"]
    assert after == before + 1


# ---------- books ----------

def test_books_list_only_returns_own_books(client, author_h):
    titles = {b["title"] for b in client.get(f"{API}/books", headers=author_h).json()}
    assert titles == {"Test Published Book", "Test Draft Book"}


def test_book_in_production_has_null_fields_not_zeros(client, author_h):
    books = {b["title"]: b for b in client.get(f"{API}/books", headers=author_h).json()}
    draft = books["Test Draft Book"]
    assert draft["is_published"] is False
    assert draft["publication_date"] is None
    assert draft["mrp"] is None
    assert draft["royalty_pending"] == 0
    assert books["Test Published Book"]["is_published"] is True
    assert books["Test Published Book"]["mrp"] == 400


def test_books_search_and_published_filter(client, author_h):
    r = client.get(f"{API}/books", params={"q": "draft"}, headers=author_h).json()
    assert [b["title"] for b in r] == ["Test Draft Book"]
    live = client.get(f"{API}/books", params={"published": "true"}, headers=author_h).json()
    assert [b["title"] for b in live] == ["Test Published Book"]
    assert client.get(f"{API}/books", params={"q": ".*"}, headers=author_h).json() == []  # regex is escaped


def test_book_detail_own(client, author_h, sync_db):
    r = client.get(f"{API}/books/{book_id(sync_db, 'T-BK1')}", headers=author_h)
    assert r.status_code == 200 and r.json()["book_code"] == "T-BK1"


def test_book_detail_of_another_author_is_404(client, author_h, sync_db):
    r = client.get(f"{API}/books/{book_id(sync_db, 'T-BK3')}", headers=author_h)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_book_detail_malformed_id_is_404(client, author_h):
    assert client.get(f"{API}/books/not-an-id", headers=author_h).status_code == 404


# ---------- ticket creation ----------

def test_create_general_ticket(client, author_h):
    t = make_ticket(client, author_h)
    assert t["status"] == "Open"
    assert t["book"] is None
    assert t["display_id"] == f"TKT-{t['ticket_number']}"
    assert t["messages"] == []
    assert t["category"] == "General Inquiry"  # placeholder until AI triage (Step 7)


def test_create_ticket_for_own_book(client, author_h, sync_db):
    t = make_ticket(client, author_h, book_id=book_id(sync_db, "T-BK1"))
    assert t["book"]["title"] == "Test Published Book"


def test_create_ticket_for_another_authors_book_is_rejected(client, author_h, sync_db):
    r = client.post(f"{API}/tickets", json={**GENERAL, "book_id": book_id(sync_db, "T-BK3")}, headers=author_h)
    assert r.status_code == 404


@pytest.mark.parametrize("bad_id", ["507f1f77bcf86cd799439011", "not-an-id"])
def test_create_ticket_with_unknown_book_is_rejected(client, author_h, bad_id):
    r = client.post(f"{API}/tickets", json={**GENERAL, "book_id": bad_id}, headers=author_h)
    assert r.status_code == 404


def test_create_ticket_rejects_privileged_fields(client, author_h, sync_db):
    other = str(sync_db.authors.find_one({"author_code": "T-AUTH2"})["_id"])
    for extra in ({"author_id": other}, {"status": "Resolved"}, {"priority": "Critical"}):
        r = client.post(f"{API}/tickets", json={**GENERAL, **extra}, headers=author_h)
        assert r.status_code == 422, extra


@pytest.mark.parametrize("override", [
    {"subject": "ab"},
    {"subject": "     "},
    {"description": "too short"},
])
def test_create_ticket_validation(client, author_h, override):
    r = client.post(f"{API}/tickets", json={**GENERAL, **override}, headers=author_h)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_ticket_numbers_are_unique_and_increasing(client, author_h):
    a, b = make_ticket(client, author_h), make_ticket(client, author_h)
    assert b["ticket_number"] > a["ticket_number"]


def test_author_ticket_response_hides_internal_fields(client, author_h):
    t = make_ticket(client, author_h)
    for hidden in ("ai_rationale", "ai_confidence", "ai_category", "assignee_id", "assignee",
                   "category_overridden", "classification_status", "author_id"):
        assert hidden not in t


# ---------- ticket reading ----------

def test_internal_notes_never_visible_to_author(client, author_h, sync_db):
    t = make_ticket(client, author_h)
    admin = sync_db.users.find_one({"email": "admin@test.dev"})
    tid = sync_db.tickets.find_one({"ticket_number": t["ticket_number"]})["_id"]
    now = datetime.now(timezone.utc)
    sync_db.ticket_messages.insert_many([
        {"ticket_id": tid, "sender_id": admin["_id"], "kind": "internal",
         "body": "SECRET internal note", "created_at": now},
        {"ticket_id": tid, "sender_id": admin["_id"], "kind": "public",
         "body": "Hello, we are looking into this.", "created_at": now + timedelta(seconds=1)},
    ])
    r = client.get(f"{API}/tickets/{t['ticket_number']}", headers=author_h)
    assert r.status_code == 200
    assert "SECRET" not in r.text
    msgs = r.json()["messages"]
    assert [m["body"] for m in msgs] == ["Hello, we are looking into this."]
    assert msgs[0]["from_support"] is True and msgs[0]["sender_label"] == "BookLeaf Support"


def test_ticket_of_another_author_is_404(client, author_h, author2_h):
    t = make_ticket(client, author2_h)
    assert client.get(f"{API}/tickets/{t['ticket_number']}", headers=author_h).status_code == 404
    assert client.get(f"{API}/tickets/{t['ticket_number']}", headers=author2_h).status_code == 200


def test_ticket_list_contains_only_own_tickets(client, author_h, author2_h):
    mine = make_ticket(client, author_h)
    theirs = make_ticket(client, author2_h)
    numbers = {i["ticket_number"] for i in client.get(f"{API}/tickets", headers=author_h).json()["items"]}
    assert mine["ticket_number"] in numbers
    assert theirs["ticket_number"] not in numbers


def test_ticket_list_status_filter(client, author_h, sync_db):
    t = make_ticket(client, author_h)
    sync_db.tickets.update_one({"ticket_number": t["ticket_number"]}, {"$set": {"status": "Resolved"}})
    resolved = client.get(f"{API}/tickets", params={"status": "Resolved"}, headers=author_h).json()["items"]
    opened = client.get(f"{API}/tickets", params={"status": "Open"}, headers=author_h).json()["items"]
    assert t["ticket_number"] in {i["ticket_number"] for i in resolved}
    assert t["ticket_number"] not in {i["ticket_number"] for i in opened}


def test_ticket_list_pagination(client, author_h):
    make_ticket(client, author_h)
    make_ticket(client, author_h)
    r = client.get(f"{API}/tickets", params={"page": 1, "page_size": 1}, headers=author_h).json()
    assert len(r["items"]) == 1
    assert r["total"] >= 2 and r["page"] == 1 and r["page_size"] == 1
    assert client.get(f"{API}/tickets", params={"page_size": 500}, headers=author_h).status_code == 422