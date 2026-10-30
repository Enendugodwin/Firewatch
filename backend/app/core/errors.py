"""Structured API errors.

Every failure returns the same envelope so the frontend has one code path::

    {"error": {"code": "...", "message": "...", "details": {...},
               "request_id": "..."}}
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger, request_id_var

logger = get_logger(__name__)

ERROR_STATUS_CODES: dict[str, int] = {
    "bad_request": 400,
    "unauthorized": 401,
    "forbidden": 403,
    "not_found": 404,
    "method_not_allowed": 405,
    "conflict": 409,
    "unprocessable": 422,
    "rate_limited": 429,
    "internal_error": 500,
    "not_implemented": 501,
    "unavailable": 503,
}


class AppError(Exception):
    """An error the API understands and can render to the standard envelope."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code or ERROR_STATUS_CODES.get(code, 400)


def error_body(
    code: str, message: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id_var.get(),
        }
    }


def not_implemented(module: str, phase: str, *, planned_for: str) -> AppError:
    """Honest placeholder for a route whose module is not built yet.

    FIREWATCH X must never serve invented observations, so unimplemented
    analytical endpoints fail loudly instead of returning sample data.
    """
    return AppError(
        "not_implemented",
        f"{module} is not implemented yet.",
        details={
            "module": module,
            "current_phase": phase,
            "planned_for_phase": planned_for,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("app_error", code=exc.code, message=exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            400: "bad_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            405: "method_not_allowed",
            429: "rate_limited",
            503: "unavailable",
        }.get(exc.status_code, "internal_error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, message),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_body(
                "unprocessable",
                "Request validation failed.",
                {"errors": exc.errors()},
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", error=str(exc))
        return JSONResponse(
            status_code=500, content=error_body("internal_error", "Internal server error.")
        )
