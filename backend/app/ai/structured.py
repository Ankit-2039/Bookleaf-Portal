import json
import logging
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.ai.client import AIClient
from app.ai.errors import AIError

logger = logging.getLogger("bookleaf.ai")
T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def extract_json(text: str) -> dict:
    """Parse the model's reply as a JSON object, tolerating code fences and stray prose."""
    cleaned = _FENCE.sub("", text.strip())
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no JSON object found")
        obj = json.loads(cleaned[start:end + 1])
    if not isinstance(obj, dict):
        raise ValueError("JSON root must be an object")
    return obj


def _describe(e: Exception) -> str:
    """Field names and error types only. Never echoes the model's output (may contain personal data)."""
    if isinstance(e, ValidationError):
        return "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['type']}" for err in e.errors())
    return "reply was not a valid JSON object"


_HINT = ("\n\nYour previous reply could not be used ({problem}). "
         "Reply again with ONLY the JSON object described above.")


async def generate_validated(
    client: AIClient,
    *,
    purpose: str,
    ticket_id,
    system: str,
    user: str,
    schema: type[T],
    max_tokens: int,
    reasoning_effort: str = "low",
    temperature: float = 0.2,
) -> T:
    """Call the model, validate against `schema`, and retry exactly once on unusable output.
    Provider errors (rate limit, timeout, ...) are NOT retried here."""
    prompt = user
    problem = "unknown"
    for attempt in (1, 2):
        try:
            resp = await client.call(
                purpose=purpose, ticket_id=ticket_id, system=system, user=prompt,
                max_tokens=max_tokens, reasoning_effort=reasoning_effort, temperature=temperature,
            )
        except AIError as e:
            if e.code == "ai_bad_output" and attempt == 1:  # provider-detected invalid JSON
                problem = "reply was not valid JSON"
                prompt = user + _HINT.format(problem=problem)
                continue
            raise
        try:
            return schema.model_validate(extract_json(resp.text))
        except ValueError as e:  # json errors and pydantic.ValidationError are both ValueErrors
            problem = _describe(e)
            logger.warning("AI output failed validation (purpose=%s attempt=%d): %s", purpose, attempt, problem)
            prompt = user + _HINT.format(problem=problem)

    raise AIError("ai_bad_output", "The AI returned a response that could not be used.",
                  retryable=True, detail=problem)