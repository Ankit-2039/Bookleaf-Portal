import asyncio
import json
import time
from contextlib import contextmanager

import pytest
from starlette.websockets import WebSocketDisconnect

from app.core.config import get_settings
from app.core.security import create_access_token
from app.realtime.manager import ConnectionManager, hub
from tests.fakes import FakeProvider

WS = "/api/v1/ws"
ADMIN = "/api/v1/admin"
AUTHOR = "/api/v1/author"
TRIAGE_JSON = json.dumps({"category": "Royalty & Payments", "priority": "High",
                          "confidence": 0.9, "rationale": "No royalty after months."})


def new_ticket(client, headers):
    body = {"book_id": None, "subject": "Royalty not received",
            "description": "I have not received any royalty for six months."}
    r = client.post(f"{AUTHOR}/tickets", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["ticket_number"]


def token_of(headers):
    return headers["Authorization"].split(" ", 1)[1]


@contextmanager
def connect(client, headers):
    with client.websocket_connect(WS) as ws:
        ws.send_json({"type": "auth", "token": token_of(headers)})
        assert ws.receive_json()["type"] == "ready"
        yield ws


def drain(ws):
    """Everything queued for this socket so far. Messages arrive in order, so a pong proves
    that no event was sent earlier that we haven't already read."""
    ws.send_json({"type": "ping"})
    out = []
    while True:
        m = ws.receive_json()
        if m["type"] == "pong":
            return out
        out.append(m)


def summary(events):
    return [(e["ticket_number"], e["reason"]) for e in events]


def reply(client, headers, n, **over):
    return client.post(f"{ADMIN}/tickets/{n}/replies", json={"body": "Thanks for writing in.", **over}, headers=headers)


def patch(client, headers, n, **fields):
    return client.patch(f"{ADMIN}/tickets/{n}", json=fields, headers=headers)


# ---------- connection & authentication ----------

def test_connection_without_auth_message_is_closed(client, monkeypatch):
    monkeypatch.setattr("app.api.ws.AUTH_TIMEOUT", 0.2)
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect(WS) as ws:
            ws.receive_json()
    assert e.value.code == 4401


@pytest.mark.parametrize("first", [
    {"type": "auth", "token": "garbage"},
    {"type": "auth"},
    {"type": "auth", "token": 123},
    {"type": "hello"},
    ["not", "an", "object"],
])
def test_bad_first_message_is_rejected(client, first):
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect(WS) as ws:
            ws.send_json(first)
            ws.receive_json()
    assert e.value.code == 4401


def test_expired_token_is_rejected(client, sync_db):
    uid = str(sync_db.users.find_one({"email": "author@test.dev"})["_id"])
    expired = create_access_token(uid, "author", expires_minutes=-1)
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect(WS) as ws:
            ws.send_json({"type": "auth", "token": expired})
            ws.receive_json()
    assert e.value.code == 4401


def test_token_of_a_deactivated_user_is_rejected(client, sync_db):
    uid = str(sync_db.users.find_one({"email": "inactive@test.dev"})["_id"])
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect(WS) as ws:
            ws.send_json({"type": "auth", "token": create_access_token(uid, "author")})
            ws.receive_json()
    assert e.value.code == 4401


def test_foreign_origin_is_refused_and_allowed_origin_connects(client, author_h):
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect(WS, headers={"origin": "http://evil.example"}) as ws:
            ws.receive_json()
    assert e.value.code == 4403

    allowed = get_settings().cors_origin_list[0]
    with client.websocket_connect(WS, headers={"origin": allowed}) as ws:
        ws.send_json({"type": "auth", "token": token_of(author_h)})
        assert ws.receive_json() == {"type": "ready", "role": "author"}


def test_ping_pong_and_admin_role(client, admin_h):
    with client.websocket_connect(WS) as ws:
        ws.send_json({"type": "auth", "token": token_of(admin_h)})
        assert ws.receive_json() == {"type": "ready", "role": "admin"}
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}


def test_connection_closes_when_the_token_expires(client, sync_db):
    uid = str(sync_db.users.find_one({"email": "author@test.dev"})["_id"])
    short_lived = create_access_token(uid, "author", expires_minutes=0.05)  # about 3 seconds
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect(WS) as ws:
            ws.send_json({"type": "auth", "token": short_lived})
            assert ws.receive_json()["type"] == "ready"
            ws.receive_json()  # blocks until the server ends the session at expiry
    assert e.value.code == 4401


def test_disconnected_clients_are_removed(client, author_h):
    with connect(client, author_h):
        assert hub.total() >= 1
    for _ in range(100):
        if hub.total() == 0:
            break
        time.sleep(0.02)
    assert hub.total() == 0


# ---------- who is told what ----------

def test_author_is_notified_of_a_public_reply_without_any_content(client, admin_h, author_h):
    n = new_ticket(client, author_h)
    with connect(client, author_h) as a:
        assert reply(client, admin_h, n, body="PUBLIC-BODY-XYZ details inside").status_code == 201
        events = drain(a)
    assert [(e["type"], e["ticket_number"], e["reason"]) for e in events] == [("ticket.updated", n, "reply")]
    assert "PUBLIC-BODY-XYZ" not in str(events) and set(events[0]) == {"type", "ticket_number", "reason", "at"}


def test_internal_notes_never_reach_the_author_but_admins_are_told(client, admin_h, author_h):
    n = new_ticket(client, author_h)
    with connect(client, author_h) as a, connect(client, admin_h) as adm:
        r = client.post(f"{ADMIN}/tickets/{n}/notes", json={"body": "SECRET-NOTE"}, headers=admin_h)
        assert r.status_code == 201
        assert drain(a) == []
        admin_events = drain(adm)
    assert summary(admin_events) == [(n, "note")] and "SECRET-NOTE" not in str(admin_events)


def test_status_and_detail_changes_notify_the_author_but_assignment_does_not(client, admin_h, author_h):
    n = new_ticket(client, author_h)
    with connect(client, author_h) as a:
        assert patch(client, admin_h, n, status="In Progress").status_code == 200
        assert summary(drain(a)) == [(n, "status")]
        assert patch(client, admin_h, n, priority="High").status_code == 200
        assert summary(drain(a)) == [(n, "details")]
        assert patch(client, admin_h, n, assignee_id="me").status_code == 200
        assert drain(a) == []  # authors never see assignees
        assert patch(client, admin_h, n, status="In Progress").status_code == 200  # no actual change
        assert drain(a) == []


def test_authors_only_receive_events_for_their_own_tickets(client, admin_h, author_h, author2_h):
    n = new_ticket(client, author_h)
    with connect(client, author_h) as a1, connect(client, author2_h) as a2:
        reply(client, admin_h, n)
        assert summary(drain(a1)) == [(n, "reply")]
        assert drain(a2) == []


def test_new_ticket_notifies_admins_and_not_other_authors(client, admin_h, author_h, author2_h):
    with connect(client, admin_h) as adm, connect(client, author2_h) as other:
        n = new_ticket(client, author_h)
        admin_events = drain(adm)
        assert drain(other) == []
    assert (n, "created") in summary(admin_events)
    assert [e["type"] for e in admin_events if e["reason"] == "created"] == ["ticket.created"]


def test_ai_triage_completion_is_pushed(client, admin_h, author_h, use_provider):
    use_provider(FakeProvider(TRIAGE_JSON))
    with connect(client, admin_h) as adm, connect(client, author_h) as a:
        n = new_ticket(client, author_h)
        assert summary(drain(adm)) == [(n, "created"), (n, "triage")]
        assert summary(drain(a)) == [(n, "triage")]


def test_failed_triage_is_pushed_to_admins_only(client, admin_h, author_h):
    # AI is unconfigured in tests, so triage fails by itself
    with connect(client, admin_h) as adm, connect(client, author_h) as a:
        n = new_ticket(client, author_h)
        assert summary(drain(adm)) == [(n, "created"), (n, "triage_failed")]
        assert drain(a) == []


def test_a_retried_reply_notifies_only_once(client, admin_h, author_h):
    n = new_ticket(client, author_h)
    with connect(client, author_h) as a:
        r1 = reply(client, admin_h, n, client_msg_id="retry-key-0001")
        r2 = reply(client, admin_h, n, client_msg_id="retry-key-0001")
        assert (r1.status_code, r2.status_code) == (201, 200)
        assert summary(drain(a)) == [(n, "reply")]


def test_rejected_operations_send_nothing(client, admin_h, author_h):
    n = new_ticket(client, author_h)
    assert patch(client, admin_h, n, status="Closed").status_code == 200
    with connect(client, author_h) as a:
        assert reply(client, admin_h, n).status_code == 409
        assert patch(client, admin_h, n, status="In Progress").status_code == 409
        assert drain(a) == []


# ---------- resilience ----------

def test_a_realtime_failure_never_breaks_the_request(client, admin_h, author_h, monkeypatch):
    async def boom(channel, payload):
        raise RuntimeError("pubsub down")

    monkeypatch.setattr(hub, "send", boom)
    n = new_ticket(client, author_h)
    assert reply(client, admin_h, n).status_code == 201
    assert patch(client, admin_h, n, priority="High").status_code == 200


def test_manager_drops_dead_sockets_and_keeps_live_ones():
    class Dead:
        async def send_json(self, payload):
            raise RuntimeError("connection reset")

    class Live:
        def __init__(self):
            self.sent = []

        async def send_json(self, payload):
            self.sent.append(payload)

    mgr, dead, live = ConnectionManager(), Dead(), Live()
    mgr.add("c", dead)
    mgr.add("c", live)
    asyncio.run(mgr.send("c", {"x": 1}))
    assert mgr.count("c") == 1 and live.sent == [{"x": 1}]
    asyncio.run(mgr.send("nobody-listens", {"x": 2}))  # unknown channel is a no-op