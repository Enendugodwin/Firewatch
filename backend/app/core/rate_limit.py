"""In-process rate limiting for public API paths.

A single-process deployment does not need Redis to stop a runaway client, and a
bounded token bucket is easy to reason about. Limits are disabled by default in
tests and configurable per environment. When the platform grows past one API
process this must move to a shared store; the response headers already expose the
contract.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

EXEMPT_PREFIXES = ("/health", "/ready", "/docs", "/openapi.json", "/redoc")


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Callable[..., Any], *, limit: int, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _client(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not request.url.path.startswith("/api"):
            return await call_next(request)
        if request.url.path.startswith(EXEMPT_PREFIXES):
            return await call_next(request)

        now = time.monotonic()
        bucket = self._hits[self._client(request)]
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()

        if len(bucket) >= self.limit:
            retry_after = int(self.window - (now - bucket[0])) + 1
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": (
                            f"More than {self.limit} requests in {self.window} seconds. "
                            "Retry after the window resets."
                        ),
                        "details": {"limit": self.limit, "window_seconds": self.window},
                        "request_id": request.headers.get("x-request-id"),
                    }
                },
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)
        response = await call_next(request)
        remaining = max(0, self.limit - len(bucket))
        response.headers.setdefault("X-RateLimit-Limit", str(self.limit))
        response.headers.setdefault("X-RateLimit-Remaining", str(remaining))
        return response
