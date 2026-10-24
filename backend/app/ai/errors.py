_HTTP_STATUS = {
    "ai_not_configured": 503,
    "ai_auth_failed": 503,
    "ai_misconfigured": 503,
    "ai_rate_limited": 429,
    "ai_timeout": 504,
    "ai_unavailable": 503,
    "ai_bad_output": 502,
    "ai_truncated": 502,
    "ai_empty_response": 502,
}


class AIError(Exception):
    """Every AI failure becomes one of these. `message` is safe to show to a user;
    `detail` is for server logs only and never contains keys or prompt/response text."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        retry_after: int | None = None,
        detail: str | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.retry_after = retry_after
        self.detail = detail

    @property
    def http_status(self) -> int:
        return _HTTP_STATUS.get(self.code, 503)