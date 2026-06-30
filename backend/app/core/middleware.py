"""HTTP middleware and exception handlers — wired in app/main.py."""
from __future__ import annotations

import logging
import secrets
import time
from collections import deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings

logger = logging.getLogger("pack")

# Per-IP in-process rate limiter for expensive POST paths. Off by default (rate_limit_per_min=0).
_RATE_PREFIXES = ("/hunts", "/parse", "/transcribe", "/documents")
_rate_hits: dict[str, deque[float]] = {}


def _rate_limited(ip: str) -> bool:
    limit = settings.rate_limit_per_min
    if limit <= 0:
        return False
    now = time.monotonic()
    dq = _rate_hits.setdefault(ip, deque())
    while dq and now - dq[0] > 60.0:
        dq.popleft()
    if len(dq) >= limit:
        return True
    dq.append(now)
    return False


async def request_context(request: Request, call_next):
    """Per-IP rate limit on expensive POSTs, then stamp every request with a short id (logged +
    returned as X-Request-ID) for tracing."""
    rid = secrets.token_hex(4)
    request.state.request_id = rid
    if request.method == "POST" and request.url.path.startswith(_RATE_PREFIXES):
        ip = request.client.host if request.client else "?"
        if _rate_limited(ip):
            return JSONResponse(
                status_code=429, content={"detail": "rate limit exceeded", "request_id": rid}
            )
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    logger.info("[%s] %s %s -> %s", rid, request.method, request.url.path, response.status_code)
    return response


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    rid = getattr(request.state, "request_id", "?")
    return JSONResponse(
        status_code=exc.status_code, content={"detail": exc.detail, "request_id": rid}
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    rid = getattr(request.state, "request_id", "?")
    logger.exception("[%s] unhandled error on %s %s", rid, request.method, request.url.path)
    return JSONResponse(
        status_code=500, content={"detail": "internal server error", "request_id": rid}
    )
