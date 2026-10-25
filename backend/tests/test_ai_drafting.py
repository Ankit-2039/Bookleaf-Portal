import asyncio
import json

import pytest

from app.ai.client import AIClient
from app.ai.drafting import check_draft, draft_response
from app.ai.errors import AIError
from tests.fakes import FakeProvider, make_ctx

TEXT_OK = (
    "Hi Priya,\n\nI'm sorry for the worry. Our records show ₹3,570 pending and ₹8,400 already paid for this book. "
    "Royalties are calculated quarterly and paid within 45 days of quarter end, and amounts under ₹1,000 roll over. "
    "Our team will look into this and get back to you within 48 hours.\n\nBookLeaf Support Team"
)


def reply(text, verify=None):
    return json.dumps({"draft": text, "verify_before_sending": verify or ["Check bank details are linked"]})


def run(provider, ctx=None):
    return asyncio.run(draft_response(AIClient(provider), ctx or make_ctx()))


def test_good_draft_has_no_warnings():
    out = run(FakeProvider(reply(TEXT_OK)))
    assert out.draft == TEXT_OK and out.warnings == []
    assert out.verify_before_sending == ["Check bank details are linked"] and out.model == "fake-model"


def test_amount_not_in_system_data_is_flagged():
    warnings = check_draft("Hi Priya, we owe you ₹9,999 in total.", make_ctx())
    assert len(warnings) == 1 and "9,999" in warnings[0]


def test_amounts_from_facts_and_the_payout_threshold_are_allowed():
    assert check_draft("You have ₹3,570 pending, ₹8,400 paid, ₹11,970 earned, MRP ₹399, minimum ₹1,000.", make_ctx()) == []


def test_placeholders_are_flagged():
    assert any("placeholder" in w for w in check_draft("Hi [Author Name], thanks.", make_ctx()))


def test_claims_of_completed_actions_are_flagged():
    warnings = check_draft("Your reprint has been triggered and the defect has been verified.", make_ctx())
    assert len(warnings) == 2


def test_future_commitments_are_not_flagged():
    assert check_draft("Our team will trigger a re-sync, which typically takes 24–48 hours.", make_ctx()) == []


def test_markdown_emphasis_is_stripped():
    out = run(FakeProvider(reply("Hi Priya, **thank you** for writing in. Our team will reply within 48 hours.")))
    assert "**" not in out.draft


def test_empty_or_tiny_drafts_are_rejected_after_one_retry():
    p = FakeProvider(reply(""), reply("ok"))
    with pytest.raises(AIError) as info:
        run(p)
    assert info.value.code == "ai_bad_output" and len(p.calls) == 2


def test_provider_failure_surfaces_as_aierror_so_manual_reply_can_continue():
    with pytest.raises(AIError) as info:
        run(FakeProvider(AIError("ai_rate_limited", "busy", retry_after=9)))
    assert info.value.code == "ai_rate_limited" and info.value.retry_after == 9


def test_draft_call_settings_and_prompt_selection():
    p = FakeProvider(reply(TEXT_OK))
    run(p)
    call = p.calls[0]
    assert call["reasoning_effort"] == "medium" and call["json_mode"] is True
    assert "45 days" in call["system"] and "stock sync" not in call["system"]

def test_payment_promises_are_flagged():
    for text in ["Our team will trigger the pending payout.", "Watch for the upcoming payment confirmation."]:
        assert any("promises a payout" in w for w in check_draft(text, make_ctx()))
    assert check_draft("Our team will investigate and update you within 48 hours.", make_ctx()) == []


def test_hypothetical_phrasing_is_not_flagged_but_real_claims_are():
    assert check_draft("The payment should have been processed by now.", make_ctx()) == []
    assert check_draft("This would have been resolved sooner.", make_ctx()) == []
    assert len(check_draft("Your payment has been processed.", make_ctx())) == 1


def test_signoff_is_moved_to_its_own_paragraph():
    out = run(FakeProvider(reply(
        "Hi Priya, thanks for writing in. Our team will reply within 48 hours. Thank you. BookLeaf Support Team")))
    assert out.draft.endswith("\n\nBookLeaf Support Team") and out.draft.count("BookLeaf Support Team") == 1