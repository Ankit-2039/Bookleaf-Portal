import logging
import time
from typing import Awaitable, Callable

from app.ai.errors import AIError
from app.ai.provider import LLMProvider, LLMResponse
from app.core.clock import utcnow

logger = logging.getLogger("bookleaf.ai")

UsageSink = Callable[[dict], Awaitable[None]]


def mongo_usage_sink(db) -> UsageSink:
    async def sink(row: dict) -> None:
        await db.ai_calls.insert_one(row)
    return sink


class AIClient:
    """Cross-cutting concerns around a provider: timing, usage logging, unexpected-error wrapping.
    Usage rows hold metadata only (no prompts, no responses, no keys)."""

    def __init__(self, provider: LLMProvider, usage_sink: UsageSink | None = None):
        self.provider = provider
        self._sink = usage_sink

    async def call(
        self,
        *,
        purpose: str,
        ticket_id,
        system: str,
        user: str,
        max_tokens: int,
        json_mode: bool = True,
        reasoning_effort: str = "low",
        temperature: float = 0.2,
    ) -> LLMResponse:
        started = time.perf_counter()
        try:
            resp = await self.provider.complete(
                system, user, max_tokens=max_tokens, json_mode=json_mode,
                reasoning_effort=reasoning_effort, temperature=temperature,
            )
        except AIError as e:
            await self._record(purpose, ticket_id, "error", started, error_code=e.code)
            raise
        except Exception as e:  # anything unexpected still degrades gracefully
            logger.exception("Unexpected failure calling the AI provider")
            await self._record(purpose, ticket_id, "error", started, error_code="ai_unexpected")
            raise AIError("ai_unavailable", "The AI service is unavailable right now.",
                          retryable=True, detail=type(e).__name__) from e

        await self._record(purpose, ticket_id, "ok", started, resp=resp)
        return resp

    async def _record(self, purpose, ticket_id, status, started, *, resp=None, error_code=None) -> None:
        if self._sink is None:
            return
        row = {
            "ticket_id": ticket_id,
            "purpose": purpose,
            "model": getattr(self.provider, "model", "unknown"),
            "status": status,
            "error_code": error_code,
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "input_tokens": resp.input_tokens if resp else None,
            "output_tokens": resp.output_tokens if resp else None,
            "created_at": utcnow(),
        }
        try:
            await self._sink(row)
        except Exception:  # usage logging must never break a real request
            logger.warning("Could not record AI usage")