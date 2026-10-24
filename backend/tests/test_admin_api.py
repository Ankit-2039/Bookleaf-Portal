from datetime import datetime, timedelta

import pytest

API = "/api/v1/admin"
AUTHOR_API = "/api/v1/author"
BODY = {"book_id": None, "subject": "Royalty not received", "description": "I have not received any royalty for six months."}


# ---------- helpers ----------

def make_ticket(client, headers, **over):
    r = client.post(f"{AUTHOR_API}/tickets", json={**BODY, **over}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["ticket_number"]


def book_id(sync_db, code):
    return str(sync_db.books.find_one({"book_code": code})["_id"])


def do_patch(client, headers, n, **fields):
    return client.patch(f"{API}/tickets/{n}", json=fields, headers=headers)


def detail(client, headers, n):
    r = client.get(f"{API}/tickets/{n}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def queue(client, headers, **params):
    r = client.get(f"{API}/tickets", params={"page_size": 100, **params}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def numbers(page):
    return [i["ticket_number"] for i in page["items"]]


def metrics(client, headers):
    r = client.get(f"{API}/metrics", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def reply(client, headers, n, **over):
    return client.post(f"{API}/tickets/{n}/replies", json={"body": "Thanks for reaching out.", **over}, headers=headers)


ADMIN_ROUTES = [
    ("GET", "/metrics"), ("GET", "/admins"), ("GET", "/tickets"), ("GET", "/tickets/1"),
    ("PATCH", "/tickets/1"), ("POST", "/tickets/1/notes"), ("POST", "/tickets/1/replies"),
    ("POST", "/tickets/1/draft"), ("POST", "/tickets/1/triage"),
]


# ---------- access control ----------

@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_routes_require_authentication(client, method, path):
    assert client.request(method, f"{API}{path}", json={}).status_code == 401


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_authors_are_forbidden_from_every_admin_route(client, author_h, method, path):
    r = client.request(method, f"{API}{path}", json={}, headers=author_h)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_author_cannot_change_priority_category_or_status(client, admin_h, author_h):
    n = make_ticket(client, author_h)
    for payload in ({"priority": "Critical"}, {"category": "General Inquiry"}, {"status": "Closed"}):
        assert do_patch(client, author_h, n, **payload).status_code == 403
    d = detail(client, admin_h, n)
    assert d["priority"] == "Medium" and d["status"] == "Open"


# ---------- queue ----------

def test_queue_lists_tickets_from_all_authors(client, admin_h, author_h, author2_h):
    a, b = make_ticket(client, author_h), make_ticket(client, author2_h)
    items = {i["ticket_number"]: i for i in queue(client, admin_h)["items"]}
    assert a in items and b in items
    assert items[b]["author"]["email"] == "author2@test.dev"
    assert items[b]["author"]["name"] == "Second Author"
    assert items[a]["status"] == "Open" and items[a]["assignee"] is None


def test_queue_filters_status_category_priority(client, admin_h, author_h):
    a, b = make_ticket(client, author_h), make_ticket(client, author_h)
    assert do_patch(client, admin_h, b, status="Resolved", category="Printing & Quality", priority="High").status_code == 200

    resolved = numbers(queue(client, admin_h, status="Resolved"))
    assert b in resolved and a not in resolved
    both = numbers(queue(client, admin_h, status=["Open", "Resolved"]))
    assert a in both and b in both
    printing = numbers(queue(client, admin_h, category="Printing & Quality"))
    assert b in printing and a not in printing
    high = numbers(queue(client, admin_h, priority="High"))
    assert b in high and a not in high


def test_queue_assignee_filter(client, admin_h, author_h):
    a, b = make_ticket(client, author_h), make_ticket(client, author_h)
    do_patch(client, admin_h, b, assignee_id="me")
    mine, unassigned = numbers(queue(client, admin_h, assignee="me")), numbers(queue(client, admin_h, assignee="unassigned"))
    assert b in mine and a not in mine
    assert a in unassigned and b not in unassigned
    assert client.get(f"{API}/tickets", params={"assignee": "garbage"}, headers=admin_h).status_code == 422


def test_queue_date_range(client, admin_h, author_h):
    n = make_ticket(client, author_h)
    day = datetime.fromisoformat(detail(client, admin_h, n)["created_at"].replace("Z", "+00:00")).date()
    assert n in numbers(queue(client, admin_h, date_from=day.isoformat(), date_to=day.isoformat()))
    assert n not in numbers(queue(client, admin_h, date_from=(day + timedelta(days=1)).isoformat()))
    assert n not in numbers(queue(client, admin_h, date_to=(day - timedelta(days=1)).isoformat()))
    bad = client.get(f"{API}/tickets", params={"date_from": "2026-02-01", "date_to": "2026-01-01"}, headers=admin_h)
    assert bad.status_code == 422


def test_queue_search(client, admin_h, author_h):
    n = make_ticket(client, author_h, subject="Zebra-crossing quarterly statement")
    assert n in numbers(queue(client, admin_h, q=f"TKT-{n}"))
    assert n in numbers(queue(client, admin_h, q=str(n)))
    assert numbers(queue(client, admin_h, q="zebra-crossing")) == [n]
    assert n in numbers(queue(client, admin_h, q="author@test.dev"))
    assert numbers(queue(client, admin_h, q="no-such-thing-xyz")) == []
    assert numbers(queue(client, admin_h, q=".*")) == []  # regex characters are escaped


def test_default_sort_is_critical_first_then_oldest_and_resolved_last(client, admin_h, author_h):
    old_medium, new_medium, critical, done = (make_ticket(client, author_h) for _ in range(4))
    do_patch(client, admin_h, critical, priority="Critical")
    do_patch(client, admin_h, done, status="Resolved", priority="Critical")
    order = numbers(queue(client, admin_h))
    assert order.index(critical) < order.index(old_medium) < order.index(new_medium)
    assert order.index(done) > order.index(new_medium)  # resolved tickets sink below every active one


def test_newest_sort(client, admin_h, author_h):
    a, b = make_ticket(client, author_h), make_ticket(client, author_h)
    order = numbers(queue(client, admin_h, sort="newest"))
    assert order.index(b) < order.index(a)


def test_queue_pagination(client, admin_h, author_h):
    for _ in range(3):
        make_ticket(client, author_h)
    page = queue(client, admin_h, page=1, page_size=2)
    assert len(page["items"]) == 2 and page["total"] >= 3 and page["page_size"] == 2
    assert client.get(f"{API}/tickets", params={"page_size": 101}, headers=admin_h).status_code == 422


# ---------- detail ----------

def test_detail_has_author_book_ai_and_empty_history(client, admin_h, author_h, sync_db):
    n = make_ticket(client, author_h, book_id=book_id(sync_db, "T-BK1"))
    d = detail(client, admin_h, n)
    assert d["author"]["email"] == "author@test.dev"
    assert d["book_detail"]["title"] == "Test Published Book"
    assert d["book_detail"]["royalty_pending"] == 600
    assert d["description"] == BODY["description"]
    assert d["classification_status"] == "failed"  # AI is unconfigured in tests; the failure is recorded honestly
    assert d["ai"]["ai_category"] is None and d["ai"]["ai_priority"] is None
    assert d["messages"] == [] and d["audit"] == []


def test_detail_unknown_ticket_is_404(client, admin_h):
    r = client.get(f"{API}/tickets/99999999", headers=admin_h)
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


# ---------- patch: status ----------

def test_status_lifecycle_and_resolved_at(client, admin_h, author_h):
    n = make_ticket(client, author_h)
    assert do_patch(client, admin_h, n, status="In Progress").json()["status"] == "In Progress"
    assert do_patch(client, admin_h, n, status="Resolved").json()["resolved_at"] is not None
    assert do_patch(client, admin_h, n, status="In Progress").json()["resolved_at"] is None  # reopened
    do_patch(client, admin_h, n, status="Resolved")
    assert do_patch(client, admin_h, n, status="Closed").json()["status"] == "Closed"
    # the author sees the persisted status
    assert client.get(f"{AUTHOR_API}/tickets/{n}", headers=author_h).json()["status"] == "Closed"


def test_invalid_status_transitions_are_rejected(client, admin_h, author_h):
    n = make_ticket(client, author_h)
    do_patch(client, admin_h, n, status="Resolved")
    r = do_patch(client, admin_h, n, status="Open")  # Resolved -> Open is not allowed
    assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_status_transition"
    do_patch(client, admin_h, n, status="Closed")
    assert do_patch(client, admin_h, n, status="In Progress").status_code == 409  # Closed is terminal
    assert detail(client, admin_h, n)["status"] == "Closed"


# ---------- patch: AI overrides ----------

def test_category_override_persists_and_keeps_ai_value(client, admin_h, author_h, sync_db):
    n = make_ticket(client, author_h)
    sync_db.tickets.update_one({"ticket_number": n}, {"$set": {
        "ai_category": "Royalty & Payments", "category": "Royalty & Payments", "classification_status": "ok"}})
    d = do_patch(client, admin_h, n, category="ISBN & Metadata Issues").json()
    assert d["category"] == "ISBN & Metadata Issues" and d["category_overridden"] is True
    assert d["ai"]["ai_category"] == "Royalty & Payments"  # original recommendation preserved
    raw = sync_db.tickets.find_one({"ticket_number": n})
    assert raw["category_overridden"] is True and raw["ai_category"] == "Royalty & Payments"
    ev = [e for e in d["audit"] if e["action"] == "category_overridden"]
    assert ev and ev[0]["old_value"] == "Royalty & Payments" and ev[0]["actor"]["name"] == "Test Admin"


def test_priority_override_persists_rank_and_keeps_ai_value(client, admin_h, author_h, sync_db):
    n = make_ticket(client, author_h)
    sync_db.tickets.update_one({"ticket_number": n}, {"$set": {"ai_priority": "Low"}})
    d = do_patch(client, admin_h, n, priority="Critical").json()
    assert d["priority"] == "Critical" and d["priority_overridden"] is True and d["ai"]["ai_priority"] == "Low"
    assert sync_db.tickets.find_one({"ticket_number": n})["priority_rank"] == 0


@pytest.mark.parametrize("payload", [
    {}, {"status": None}, {"status": "Banana"}, {"category": "Not A Category"}, {"author_id": "x"},
])
def test_patch_validation(client, admin_h, author_h, payload):
    n = make_ticket(client, author_h)
    r = do_patch(client, admin_h, n, **payload)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


# ---------- patch: assignment ----------

def test_assignment(client, admin_h, admin2_h, author_h, sync_db):
    n = make_ticket(client, author_h)
    assert do_patch(client, admin_h, n, assignee_id="me").json()["assignee"]["name"] == "Test Admin"
    admin2 = str(sync_db.users.find_one({"email": "admin2@test.dev"})["_id"])
    assert do_patch(client, admin_h, n, assignee_id=admin2).json()["assignee"]["name"] == "Second Admin"
    d = do_patch(client, admin_h, n, assignee_id=None).json()
    assert d["assignee"] is None
    assert [e["action"] for e in d["audit"]].count("assigned") == 3

    author_user = str(sync_db.users.find_one({"email": "author@test.dev"})["_id"])
    assert do_patch(client, admin_h, n, assignee_id=author_user).status_code == 422  # must be an admin
    assert do_patch(client, admin_h, n, assignee_id="not-an-id").status_code == 422


# ---------- internal notes ----------

def test_internal_note_is_admin_only_and_does_not_touch_updated_at(client, admin_h, author_h):
    n = make_ticket(client, author_h)
    before = detail(client, admin_h, n)["updated_at"]
    r = client.post(f"{API}/tickets/{n}/notes", json={"body": "SECRET: bank details look wrong"}, headers=admin_h)
    assert r.status_code == 201 and r.json()["kind"] == "internal"

    d = detail(client, admin_h, n)
    assert [m["kind"] for m in d["messages"]] == ["internal"]
    assert d["updated_at"] == before
    assert "note_added" in [e["action"] for e in d["audit"]]

    author_view = client.get(f"{AUTHOR_API}/tickets/{n}", headers=author_h)
    assert "SECRET" not in author_view.text and author_view.json()["messages"] == []
    assert "SECRET" not in client.get(f"{AUTHOR_API}/tickets", headers=author_h).text


def test_note_validation(client, admin_h, author_h):
    n = make_ticket(client, author_h)
    assert client.post(f"{API}/tickets/{n}/notes", json={"body": "   "}, headers=admin_h).status_code == 422


# ---------- public replies ----------

def test_public_reply_reaches_author_advances_status_and_assigns(client, admin_h, author_h):
    n = make_ticket(client, author_h)
    r = reply(client, admin_h, n, body="Hello, we are on it.")
    assert r.status_code == 201 and r.json()["kind"] == "public"

    d = detail(client, admin_h, n)
    assert d["status"] == "In Progress" and d["assignee"]["name"] == "Test Admin"
    assert {"reply_sent", "status_changed", "assigned"} <= {e["action"] for e in d["audit"]}

    a = client.get(f"{AUTHOR_API}/tickets/{n}", headers=author_h).json()
    assert a["status"] == "In Progress"
    assert [(m["body"], m["from_support"]) for m in a["messages"]] == [("Hello, we are on it.", True)]


def test_reply_keeps_existing_assignee(client, admin_h, admin2_h, author_h):
    n = make_ticket(client, author_h)
    do_patch(client, admin2_h, n, assignee_id="me")
    reply(client, admin_h, n)
    assert detail(client, admin_h, n)["assignee"]["name"] == "Second Admin"


def test_reply_retry_with_same_client_msg_id_is_idempotent(client, admin_h, author_h):
    n = make_ticket(client, author_h)
    r1 = reply(client, admin_h, n, body="Same message", client_msg_id="retry-key-0001")
    r2 = reply(client, admin_h, n, body="Same message", client_msg_id="retry-key-0001")
    assert r1.status_code == 201 and r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]
    assert len(client.get(f"{AUTHOR_API}/tickets/{n}", headers=author_h).json()["messages"]) == 1


def test_reply_can_resolve_ticket(client, admin_h, author_h):
    n = make_ticket(client, author_h)
    assert reply(client, admin_h, n, body="All sorted.", set_status="Resolved").status_code == 201
    d = detail(client, admin_h, n)
    assert d["status"] == "Resolved" and d["resolved_at"] is not None


def test_reply_with_invalid_status_change_stores_nothing(client, admin_h, author_h):
    n = make_ticket(client, author_h)
    do_patch(client, admin_h, n, status="Resolved")
    assert reply(client, admin_h, n, set_status="Open").status_code == 409
    assert detail(client, admin_h, n)["messages"] == []


def test_cannot_reply_to_closed_ticket(client, admin_h, author_h):
    n = make_ticket(client, author_h)
    do_patch(client, admin_h, n, status="Closed")
    r = reply(client, admin_h, n)
    assert r.status_code == 409 and r.json()["error"]["code"] == "ticket_closed"


@pytest.mark.parametrize("payload", [
    {"body": "   "}, {"body": "ok", "extra": 1}, {"body": "ok", "set_status": "Banana"},
])
def test_reply_validation(client, admin_h, author_h, payload):
    n = make_ticket(client, author_h)
    assert client.post(f"{API}/tickets/{n}/replies", json=payload, headers=admin_h).status_code == 422


def test_ai_drafted_flag_is_recorded_for_admins_and_hidden_from_authors(client, admin_h, author_h):
    n = make_ticket(client, author_h)
    reply(client, admin_h, n, from_ai_draft=True)
    assert detail(client, admin_h, n)["messages"][0]["ai_drafted"] is True
    assert "ai_drafted" not in client.get(f"{AUTHOR_API}/tickets/{n}", headers=author_h).text


# ---------- metrics & helpers ----------

def test_metrics_reflect_real_ticket_changes(client, admin_h, author_h):
    m0 = metrics(client, admin_h)
    n = make_ticket(client, author_h)
    m1 = metrics(client, admin_h)
    assert m1["total_tickets"] == m0["total_tickets"] + 1
    assert m1["open_tickets"] == m0["open_tickets"] + 1
    assert m1["unassigned_unresolved"] == m0["unassigned_unresolved"] + 1
    assert m1["urgent_unresolved"] == m0["urgent_unresolved"]

    do_patch(client, admin_h, n, priority="High", assignee_id="me")
    m2 = metrics(client, admin_h)
    assert m2["urgent_unresolved"] == m1["urgent_unresolved"] + 1
    assert m2["unassigned_unresolved"] == m1["unassigned_unresolved"] - 1
    assert m2["assigned_to_me"] == m1["assigned_to_me"] + 1

    do_patch(client, admin_h, n, status="Resolved")
    m3 = metrics(client, admin_h)
    assert m3["resolved_tickets"] == m2["resolved_tickets"] + 1
    assert m3["urgent_unresolved"] == m2["urgent_unresolved"] - 1  # resolved tickets are no longer urgent
    assert m3["avg_resolution_hours"] is not None and m3["avg_resolution_hours"] >= 0


def test_metrics_consistency_and_highlight_lists(client, admin_h, author_h):
    make_ticket(client, author_h)
    m = metrics(client, admin_h)
    assert m["total_tickets"] == m["open_tickets"] + m["in_progress_tickets"] + m["resolved_tickets"] + m["closed_tickets"]
    assert 1 <= len(m["urgent_queue"]) <= 5 and all(t["status"] in ("Open", "In Progress") for t in m["urgent_queue"])
    waiting = [t["created_at"] for t in m["longest_waiting"]]
    assert waiting == sorted(waiting)  # oldest first


def test_admin_list_contains_only_admins(client, admin_h):
    names = {a["name"] for a in client.get(f"{API}/admins", headers=admin_h).json()}
    assert names == {"Test Admin", "Second Admin"}