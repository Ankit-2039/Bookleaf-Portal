import json
from datetime import datetime, timezone

import pytest

from app.ai.errors import AIError
from tests.fakes import FakeProvider

ADMIN = "/api/v1/admin"
AUTHOR = "/api/v1/author"

TRIAGE_JSON = json.dumps({"category": "Royalty & Payments", "priority": "High",
                          "confidence": 0.9, "rationale": "No royalty after months."})
DRAFT_TEXT = ("Hi Test,\n\nI'm sorry about the delay. Our team will look into this and get back to you "
              "within 48 hours.\n\nBookLeaf Support Team")
DRAFT_JSON = json.dumps({"draft": DRAFT_TEXT, "verify_before_sending": ["Check bank details"]})


def new_ticket(client, headers, book=None, **over):
    body = {"book_id": book, "subject": "Royalty not received",
            "description": "I have not received any royalty for six months.", **over}
    r = client.post(f"{AUTHOR}/tickets", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["ticket_number"]


def detail(client, headers, n):
    r = client.get(f"{ADMIN}/tickets/{n}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def book_id(sync_db, code):
    return str(sync_db.books.find_one({"book_code": code})["_id"])


def draft(client, headers, n):
    return client.post(f"{ADMIN}/tickets/{n}/draft", headers=headers)


def retriage(client, headers, n):
    return client.post(f"{ADMIN}/tickets/{n}/triage", headers=headers)


class RacingProvider(FakeProvider):
    """Runs a callback in the middle of the LLM call: simulates an admin acting while AI is thinking."""
    def __init__(self, outcome, on_call):
        super().__init__(outcome)
        self.on_call = on_call

    async def complete(self, system, user, **kw):
        self.on_call()
        return await super().complete(system, user, **kw)


# ---------- ticket creation + background triage ----------

def test_ticket_is_created_when_ai_is_not_configured(client, admin_h, author_h):
    n = new_ticket(client, author_h)
    d = detail(client, admin_h, n)
    assert d["classification_status"] == "failed" and d["ai"]["error_code"] == "ai_not_configured"
    assert d["category"] == "General Inquiry" and d["priority"] == "Medium"  # placeholders, not AI results
    assert d["ai"]["ai_category"] is None
    assert n in {t["ticket_number"] for t in client.get(f"{AUTHOR}/tickets", headers=author_h).json()["items"]}


def test_ticket_is_created_when_ai_is_rate_limited(client, admin_h, author_h, use_provider):
    use_provider(FakeProvider(AIError("ai_rate_limited", "busy", retryable=True, retry_after=5)))
    n = new_ticket(client, author_h)
    d = detail(client, admin_h, n)
    assert d["classification_status"] == "failed" and d["ai"]["error_code"] == "ai_rate_limited"


def test_ticket_is_created_when_ai_returns_garbage(client, admin_h, author_h, use_provider):
    p = use_provider(FakeProvider("garbage", "still garbage"))
    n = new_ticket(client, author_h)
    d = detail(client, admin_h, n)
    assert d["classification_status"] == "failed" and d["ai"]["error_code"] == "ai_bad_output"
    assert len(p.calls) == 2  # exactly one repair retry


def test_successful_triage_sets_category_priority_and_ai_fields(client, admin_h, author_h, sync_db, use_provider):
    p = use_provider(FakeProvider(TRIAGE_JSON))
    n = new_ticket(client, author_h, book=book_id(sync_db, "T-BK1"))
    assert len(p.calls) == 1  # triaged exactly once

    d = detail(client, admin_h, n)
    assert d["classification_status"] == "ok"
    assert d["category"] == "Royalty & Payments" and d["priority"] == "High"
    assert d["ai"]["ai_category"] == "Royalty & Payments" and d["ai"]["ai_confidence"] == 0.9
    assert d["ai"]["ai_rationale"] == "No royalty after months." and d["ai"]["classified_at"] is not None
    assert d["category_overridden"] is False and d["priority_overridden"] is False
    assert sync_db.tickets.find_one({"ticket_number": n})["priority_rank"] == 1

    events = [e for e in d["audit"] if e["action"] == "ai_triaged"]
    assert len(events) == 1 and events[0]["actor"] is None  # system, not an admin

    queue = client.get(f"{ADMIN}/tickets", params={"priority": "High", "page_size": 100}, headers=admin_h).json()
    assert n in [i["ticket_number"] for i in queue["items"]]


def test_triage_prompt_has_no_author_email_and_authors_never_see_ai_fields(client, author_h, use_provider):
    p = use_provider(FakeProvider(TRIAGE_JSON))
    n = new_ticket(client, author_h)
    assert "author@test.dev" not in p.calls[0]["user"] + p.calls[0]["system"]
    text = client.get(f"{AUTHOR}/tickets/{n}", headers=author_h).text
    assert "No royalty after months." not in text and "ai_confidence" not in text


# ---------- overrides are never overwritten ----------

def test_admin_override_survives_ai_rerun(client, admin_h, author_h, use_provider):
    n = new_ticket(client, author_h)  # AI unconfigured -> failed
    client.patch(f"{ADMIN}/tickets/{n}", json={"category": "Printing & Quality", "priority": "Low"}, headers=admin_h)
    use_provider(FakeProvider(TRIAGE_JSON))
    assert retriage(client, admin_h, n).status_code == 200
    d = detail(client, admin_h, n)
    assert d["category"] == "Printing & Quality" and d["priority"] == "Low"      # admin's choices stand
    assert d["ai"]["ai_category"] == "Royalty & Payments" and d["ai"]["ai_priority"] == "High"  # AI view kept
    assert d["category_overridden"] and d["priority_overridden"] and d["classification_status"] == "ok"


def test_partial_override_only_protects_the_overridden_field(client, admin_h, author_h, sync_db, use_provider):
    n = new_ticket(client, author_h)
    client.patch(f"{ADMIN}/tickets/{n}", json={"category": "ISBN & Metadata Issues"}, headers=admin_h)
    use_provider(FakeProvider(TRIAGE_JSON))
    retriage(client, admin_h, n)
    d = detail(client, admin_h, n)
    assert d["category"] == "ISBN & Metadata Issues"   # protected
    assert d["priority"] == "High"                      # not overridden, so the AI value applies
    assert sync_db.tickets.find_one({"ticket_number": n})["priority_rank"] == 1


def test_override_made_while_the_llm_call_is_in_flight_still_wins(client, admin_h, author_h, sync_db, use_provider):
    n = new_ticket(client, author_h)

    def admin_overrides_mid_call():
        sync_db.tickets.update_one({"ticket_number": n},
                                   {"$set": {"category": "Printing & Quality", "category_overridden": True}})

    use_provider(RacingProvider(TRIAGE_JSON, admin_overrides_mid_call))
    assert retriage(client, admin_h, n).status_code == 200
    d = detail(client, admin_h, n)
    assert d["category"] == "Printing & Quality"
    assert d["ai"]["ai_category"] == "Royalty & Payments"
    assert d["priority"] == "High"


# ---------- retry ----------

def test_failed_triage_can_be_retried(client, admin_h, author_h, use_provider):
    n = new_ticket(client, author_h)
    assert detail(client, admin_h, n)["classification_status"] == "failed"
    use_provider(FakeProvider(TRIAGE_JSON))
    r = retriage(client, admin_h, n)
    assert r.status_code == 200 and r.json()["classification_status"] == "ok"
    assert r.json()["ai"]["error_code"] is None


def test_failed_retry_does_not_downgrade_an_earlier_good_triage(client, admin_h, author_h, use_provider):
    use_provider(FakeProvider(TRIAGE_JSON))
    n = new_ticket(client, author_h)
    use_provider(FakeProvider(AIError("ai_rate_limited", "busy", retryable=True, retry_after=3)))
    r = retriage(client, admin_h, n)
    assert r.status_code == 429 and r.json()["error"]["code"] == "ai_rate_limited"
    d = detail(client, admin_h, n)
    assert d["classification_status"] == "ok" and d["category"] == "Royalty & Payments"


def test_triage_endpoints_are_admin_only(client, author_h):
    n = new_ticket(client, author_h)
    assert retriage(client, author_h, n).status_code == 403
    assert draft(client, author_h, n).status_code == 403
    assert client.post(f"{ADMIN}/tickets/{n}/draft").status_code == 401


# ---------- drafting ----------

def test_draft_success_returns_text_warnings_and_persists_nothing(client, admin_h, author_h, sync_db, use_provider):
    n = new_ticket(client, author_h)
    p = use_provider(FakeProvider(DRAFT_JSON))
    r = draft(client, admin_h, n)
    assert r.status_code == 200
    body = r.json()
    assert body["draft"] == DRAFT_TEXT and body["verify_before_sending"] == ["Check bank details"]
    assert body["warnings"] == [] and body["model"] == "fake-model" and body["generated_at"]

    assert detail(client, admin_h, n)["messages"] == []                              # not saved
    assert client.get(f"{AUTHOR}/tickets/{n}", headers=author_h).json()["messages"] == []  # not sent

    tid = sync_db.tickets.find_one({"ticket_number": n})["_id"]
    rows = list(sync_db.ai_calls.find({"ticket_id": tid, "purpose": "draft"}))
    assert len(rows) == 1 and rows[0]["status"] == "ok" and rows[0]["input_tokens"] == 120
    assert not {"prompt", "user", "system", "response", "text", "draft"} & set(rows[0])
    assert len(p.calls) == 1


def test_draft_prompt_has_book_facts_and_public_history_but_never_internal_notes(client, admin_h, author_h, sync_db, use_provider):
    n = new_ticket(client, author_h, book=book_id(sync_db, "T-BK1"))
    client.post(f"{ADMIN}/tickets/{n}/notes", json={"body": "SECRET-NOTE-ZZZ"}, headers=admin_h)
    client.post(f"{ADMIN}/tickets/{n}/replies", json={"body": "PUBLIC-REPLY-QQQ please send details."}, headers=admin_h)
    p = use_provider(FakeProvider(DRAFT_JSON))
    assert draft(client, admin_h, n).status_code == 200
    system, user = p.calls[0]["system"], p.calls[0]["user"]
    assert "SECRET-NOTE-ZZZ" not in system + user
    assert "PUBLIC-REPLY-QQQ" in user
    assert "Test Published Book" in user and "₹600" in user
    assert "author@test.dev" not in system + user


def test_draft_uses_full_kb_until_category_is_confirmed_then_only_the_relevant_part(client, admin_h, author_h, use_provider):
    n = new_ticket(client, author_h)  # triage failed -> category unconfirmed
    p = use_provider(FakeProvider(DRAFT_JSON))
    draft(client, admin_h, n)
    assert "stock sync" in p.calls[0]["system"] and "45 days" in p.calls[0]["system"]
    assert "not yet confirmed" in p.calls[0]["user"]

    client.patch(f"{ADMIN}/tickets/{n}", json={"category": "Royalty & Payments"}, headers=admin_h)
    p2 = use_provider(FakeProvider(DRAFT_JSON))
    draft(client, admin_h, n)
    assert "45 days" in p2.calls[0]["system"] and "stock sync" not in p2.calls[0]["system"]


def test_draft_failure_returns_safe_error_and_manual_reply_still_works(client, admin_h, author_h, use_provider):
    n = new_ticket(client, author_h)
    use_provider(FakeProvider(AIError("ai_rate_limited", "busy", retryable=True, retry_after=9, detail="secret-detail")))
    r = draft(client, admin_h, n)
    assert r.status_code == 429 and r.headers["retry-after"] == "9"
    err = r.json()["error"]
    assert err["code"] == "ai_rate_limited" and "manually" in err["message"] and "secret-detail" not in r.text

    sent = client.post(f"{ADMIN}/tickets/{n}/replies", json={"body": "Manual reply while AI is down."}, headers=admin_h)
    assert sent.status_code == 201
    assert client.get(f"{AUTHOR}/tickets/{n}", headers=author_h).json()["messages"][0]["body"] == "Manual reply while AI is down."


@pytest.mark.parametrize("error,status", [
    (AIError("ai_timeout", "slow", retryable=True), 504),
    (AIError("ai_unavailable", "down", retryable=True), 503),
    (AIError("ai_auth_failed", "bad key"), 503),
])
def test_draft_error_statuses(client, admin_h, author_h, use_provider, error, status):
    n = new_ticket(client, author_h)
    use_provider(FakeProvider(error))
    r = draft(client, admin_h, n)
    assert r.status_code == status and r.json()["error"]["code"] == error.code


def test_draft_with_unusable_model_output_is_a_502(client, admin_h, author_h, use_provider):
    n = new_ticket(client, author_h)
    use_provider(FakeProvider("nope", "nope again"))
    r = draft(client, admin_h, n)
    assert r.status_code == 502 and r.json()["error"]["code"] == "ai_bad_output"


def test_draft_when_ai_not_configured_is_a_clean_503(client, admin_h, author_h):
    n = new_ticket(client, author_h)
    r = draft(client, admin_h, n)
    assert r.status_code == 503 and r.json()["error"]["code"] == "ai_not_configured"


def test_draft_is_rejected_for_closed_and_unknown_tickets(client, admin_h, author_h, use_provider):
    n = new_ticket(client, author_h)
    client.patch(f"{ADMIN}/tickets/{n}", json={"status": "Closed"}, headers=admin_h)
    p = use_provider(FakeProvider(DRAFT_JSON))
    assert draft(client, admin_h, n).status_code == 409
    assert draft(client, admin_h, 99999999).status_code == 404
    assert p.calls == []


def test_draft_limit_per_ticket_per_hour(client, admin_h, author_h, sync_db, use_provider):
    n = new_ticket(client, author_h)
    tid = sync_db.tickets.find_one({"ticket_number": n})["_id"]
    now = datetime.now(timezone.utc)
    sync_db.ai_calls.insert_many([
        {"ticket_id": tid, "purpose": "draft", "status": "ok", "model": "x", "created_at": now} for _ in range(10)
    ])
    p = use_provider(FakeProvider(DRAFT_JSON))
    r = draft(client, admin_h, n)
    assert r.status_code == 429 and r.json()["error"]["code"] == "draft_limit_reached"
    assert p.calls == []  # blocked before any spend