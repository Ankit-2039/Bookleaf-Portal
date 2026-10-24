import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("bookleaf")

_STATUS_CODES = {
    400: "bad_request",
    401: "not_authenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
}


class AppError(Exception):
    """Raise this from services/routes for any expected failure."""

    def __init__(self, status_code: int, code: str, message: str, headers: dict | None = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers


def _response(status: int, code: str, message: str, details=None, headers=None) -> JSONResponse:
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status, content=body, headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return _response(exc.status_code, exc.code, exc.message, headers=exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        code = _STATUS_CODES.get(exc.status_code, "http_error")
        return _response(exc.status_code, code, str(exc.detail), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in e["loc"][1:]) or str(e["loc"][0]), "message": e["msg"]}
            for e in exc.errors()
        ]
        return _response(422, "validation_error", "Request validation failed.", details)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        # Full detail goes to server logs only; the client gets a safe generic message.
        logger.exception("Unhandled error")
        return _response(500, "internal_error", "Something went wrong. Please try again.")