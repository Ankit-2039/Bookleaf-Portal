import asyncio
from types import SimpleNamespace

import httpx
import pytest
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
)

from app.ai.errors import AIError
from app.ai.provider import OpenAICompatProvider, UnconfiguredProvider

REQ = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
SECRET = "sk-secret-123"


def _resp(status, headers=None):
    return httpx.Response(status, headers=headers or {}, request=REQ)


class _Completions:
    def __init__(self, outcome):
        self.outcome, self.kwargs = outcome, None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def make_provider(outcome, model="openai/gpt-oss-120b"):
    p = OpenAICompatProvider(model=model, api_key=SECRET, base_url="http://localhost:9", timeout=5)
    comp = _Completions(outcome)
    p._client = SimpleNamespace(chat=SimpleNamespace(completions=comp))
    return p, comp


def ok(content="{}", finish="stop"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish)],
        usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7),
    )


def call(provider, **kw):
    return asyncio.run(provider.complete("sys", "user", max_tokens=100, **kw))


CASES = [
    (APITimeoutError(REQ), "ai_timeout"),
    (APIConnectionError(request=REQ), "ai_unavailable"),
    (RateLimitError("slow down", response=_resp(429, {"retry-after": "7"}), body=None), "ai_rate_limited"),
    (AuthenticationError("bad key", response=_resp(401), body=None), "ai_auth_failed"),
    (InternalServerError("boom", response=_resp(500), body=None), "ai_unavailable"),
    (NotFoundError("no such model", response=_resp(404), body=None), "ai_misconfigured"),
    (BadRequestError("json_validate_failed", response=_resp(400), body=None), "ai_bad_output"),
]


@pytest.mark.parametrize("exc,code", CASES)
def test_provider_errors_are_mapped_and_leak_nothing(exc, code):
    p, _ = make_provider(exc)
    with pytest.raises(AIError) as info:
        call(p)
    err = info.value
    assert err.code == code
    assert SECRET not in str(err) and SECRET not in (err.detail or "")
    assert "bad key" not in err.message and "no such model" not in err.message


def test_rate_limit_exposes_retry_after():
    p, _ = make_provider(CASES[2][0])
    with pytest.raises(AIError) as info:
        call(p)
    assert info.value.retry_after == 7 and info.value.retryable


def test_success_returns_text_and_token_usage():
    p, _ = make_provider(ok('{"a": 1}'))
    r = call(p)
    assert r.text == '{"a": 1}' and r.input_tokens == 11 and r.output_tokens == 7


def test_empty_content_and_truncation_are_distinct_errors():
    p, _ = make_provider(ok(content=""))
    with pytest.raises(AIError) as e1:
        call(p)
    assert e1.value.code == "ai_empty_response"
    p, _ = make_provider(ok(content="", finish="length"))
    with pytest.raises(AIError) as e2:
        call(p)
    assert e2.value.code == "ai_truncated"


def test_request_parameters():
    p, comp = make_provider(ok())
    call(p, json_mode=True, reasoning_effort="low")
    assert comp.kwargs["response_format"] == {"type": "json_object"}
    assert comp.kwargs["extra_body"] == {"reasoning_effort": "low"}
    assert comp.kwargs["max_completion_tokens"] == 100

    p, comp = make_provider(ok(), model="some-other-model")
    call(p, json_mode=False)
    assert "extra_body" not in comp.kwargs and "response_format" not in comp.kwargs


def test_unconfigured_provider_fails_cleanly():
    with pytest.raises(AIError) as info:
        asyncio.run(UnconfiguredProvider().complete("s", "u", max_tokens=10))
    assert info.value.code == "ai_not_configured" and info.value.http_status == 503


def test_http_status_mapping():
    assert AIError("ai_rate_limited", "x").http_status == 429
    assert AIError("ai_timeout", "x").http_status == 504
    assert AIError("ai_bad_output", "x").http_status == 502
    assert AIError("something_new", "x").http_status == 503