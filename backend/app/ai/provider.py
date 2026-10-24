import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)

from app.ai.errors import AIError
from app.core.config import Settings, get_settings

logger = logging.getLogger("bookleaf.ai")


@dataclass
class LLMResponse:
    text: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    finish_reason: str | None


class LLMProvider(Protocol):
    model: str

    async def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int,
        json_mode: bool = True,
        reasoning_effort: str = "low",
        temperature: float = 0.2,
    ) -> LLMResponse: ...


def _status(e: Exception) -> str:
    # Deliberately excludes the exception message: it could echo request content.
    return f"{type(e).__name__} status={getattr(e, 'status_code', None)}"


class OpenAICompatProvider:
    """Any OpenAI-compatible endpoint (Groq, OpenAI, ...), configured purely by env vars."""

    def __init__(self, *, model: str, api_key: str, base_url: str, timeout: float):
        self.model = model
        # max_retries=1: the SDK retries once (with backoff) on 429/5xx/connection errors,
        # then we degrade gracefully instead of making the admin wait.
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=1)

    async def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int,
        json_mode: bool = True,
        reasoning_effort: str = "low",
        temperature: float = 0.2,
    ) -> LLMResponse:
        kwargs: dict = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_completion_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if "gpt-oss" in self.model:  # reasoning models: hidden reasoning counts toward max tokens
            kwargs["extra_body"] = {"reasoning_effort": reasoning_effort}

        try:
            resp = await self._client.chat.completions.create(**kwargs)
        except APITimeoutError as e:  # must precede APIConnectionError (its parent)
            raise AIError("ai_timeout", "The AI service took too long to respond.",
                          retryable=True, detail=_status(e)) from e
        except RateLimitError as e:
            retry_after = None
            try:
                retry_after = int(float(e.response.headers.get("retry-after", "")))
            except (ValueError, TypeError, AttributeError):
                pass
            raise AIError("ai_rate_limited", "The AI service is busy (rate limit reached).",
                          retryable=True, retry_after=retry_after, detail=_status(e)) from e
        except (AuthenticationError, PermissionDeniedError) as e:
            logger.error("AI provider rejected the credentials (%s)", _status(e))
            raise AIError("ai_auth_failed", "The AI service is not configured correctly.",
                          detail=_status(e)) from e
        except BadRequestError as e:
            if "json_validate_failed" in str(e):  # the model produced invalid JSON in JSON mode
                raise AIError("ai_bad_output", "The AI returned a response that could not be used.",
                              retryable=True, detail=_status(e)) from e
            raise AIError("ai_misconfigured", "The AI service is not configured correctly.",
                          detail=_status(e)) from e
        except NotFoundError as e:
            raise AIError("ai_misconfigured", "The AI service is not configured correctly.",
                          detail=_status(e)) from e
        except APIConnectionError as e:
            raise AIError("ai_unavailable", "The AI service is unavailable right now.",
                          retryable=True, detail=_status(e)) from e
        except APIStatusError as e:
            raise AIError("ai_unavailable", "The AI service is unavailable right now.",
                          retryable=True, detail=_status(e)) from e

        if not resp.choices:
            raise AIError("ai_empty_response", "The AI returned an empty response.", retryable=True)
        choice = resp.choices[0]
        text = (choice.message.content or "").strip()
        usage = getattr(resp, "usage", None)

        if not text:
            if choice.finish_reason == "length":
                raise AIError("ai_truncated", "The AI ran out of room before finishing its answer.",
                              detail="finish_reason=length (token budget exhausted, likely by reasoning)")
            raise AIError("ai_empty_response", "The AI returned an empty response.", retryable=True)

        return LLMResponse(
            text=text,
            model=self.model,
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
            finish_reason=choice.finish_reason,
        )


class UnconfiguredProvider:
    """Used when no API key is set: every call fails cleanly and tickets/manual replies still work."""

    model = "unconfigured"

    async def complete(self, system, user, **kwargs) -> LLMResponse:
        raise AIError("ai_not_configured", "AI assistance is not configured. You can still reply manually.")


def build_provider(settings: Settings) -> LLMProvider:
    if not settings.llm_api_key:
        return UnconfiguredProvider()
    return OpenAICompatProvider(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
    )


@lru_cache
def get_provider() -> LLMProvider:
    return build_provider(get_settings())