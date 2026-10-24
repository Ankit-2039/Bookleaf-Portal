import asyncio

import pytest

from app.ai.client import AIClient
from app.ai.errors import AIError
from app.ai.triage import triage_ticket
from app.models.enums import TicketCategory, TicketPriority
from tests.fakes import FakeProvider, make_ctx

GOOD = '{"category": "Royalty & Payments", "priority": "High", "confidence": 0.9, "rationale": "No royalty after months."}'
BAD_CATEGORY = '{"category": "Billing", "priority": "High", "confidence": 0.5, "rationale": "x"}'


def run(provider, sink=None, ctx=None):
    return asyncio.run(triage_ticket(AIClient(provider, usage_sink=sink), ctx or make_ctx()))


def test_valid_reply_is_parsed():
    r = run(FakeProvider(GOOD))
    assert r.category == TicketCategory.ROYALTY and r.priority == TicketPriority.HIGH
    assert r.confidence == 0.9


def test_tolerates_fences_case_and_percent_confidence():
    reply = '```json\n{"category": "printing & quality", "priority": "medium", "confidence": 85, "rationale": "Blurry print."}\n```'
    r = run(FakeProvider(reply))
    assert r.category == TicketCategory.PRINTING and r.priority == TicketPriority.MEDIUM
    assert r.confidence == pytest.approx(0.85)


def test_invalid_category_is_rejected_then_retried_once_without_echoing_output():
    p = FakeProvider(BAD_CATEGORY, GOOD)
    r = run(p)
    assert r.category == TicketCategory.ROYALTY and len(p.calls) == 2
    assert "could not be used" in p.calls[1]["user"]
    assert "Billing" not in p.calls[1]["user"]  # the hint never echoes model output


def test_two_unusable_replies_raise_after_exactly_two_calls():
    p = FakeProvider(BAD_CATEGORY, "not json at all")
    with pytest.raises(AIError) as info:
        run(p)
    assert info.value.code == "ai_bad_output" and len(p.calls) == 2


def test_provider_failures_are_not_retried():
    p = FakeProvider(AIError("ai_rate_limited", "busy", retryable=True, retry_after=5), GOOD)
    with pytest.raises(AIError) as info:
        run(p)
    assert info.value.code == "ai_rate_limited" and len(p.calls) == 1


def test_provider_detected_bad_json_gets_one_retry():
    p = FakeProvider(AIError("ai_bad_output", "bad", retryable=True), GOOD)
    assert run(p).priority == TicketPriority.HIGH and len(p.calls) == 2


def test_out_of_range_confidence_is_rejected():
    reply = '{"category": "General Inquiry", "priority": "Low", "confidence": 250, "rationale": "x"}'
    with pytest.raises(AIError):
        run(FakeProvider(reply, reply))


def test_usage_rows_hold_metadata_only():
    rows = []

    async def sink(row):
        rows.append(row)

    run(FakeProvider(GOOD), sink=sink)
    assert rows[0]["purpose"] == "triage" and rows[0]["status"] == "ok" and rows[0]["model"] == "fake-model"
    assert rows[0]["input_tokens"] == 120 and rows[0]["output_tokens"] == 40
    assert not {"prompt", "user", "system", "response", "text"} & set(rows[0])

    rows.clear()
    with pytest.raises(AIError):
        run(FakeProvider(AIError("ai_timeout", "slow")), sink=sink)
    assert rows[0]["status"] == "error" and rows[0]["error_code"] == "ai_timeout"


def test_a_failing_usage_sink_never_breaks_the_call():
    async def broken(row):
        raise RuntimeError("db down")

    assert run(FakeProvider(GOOD), sink=broken).category == TicketCategory.ROYALTY


def test_triage_uses_cheap_settings():
    p = FakeProvider(GOOD)
    run(p)
    assert p.calls[0]["reasoning_effort"] == "low" and p.calls[0]["max_tokens"] <= 1500