"""FastAPI dependency providers — the single place where app.state is touched by route code.

All route handlers receive these via Depends(), never via request.app.state directly.
Tests override them with app.dependency_overrides[get_repo] = lambda: FakeRepo().
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import HTTPException, Request, UploadFile, status

from app.bus.redis_stream import EventBus
from app.config import settings
from app.db.repo import Repo
from app.engine.registry import HuntRegistry
from app.qwen.client import QwenClient

logger = logging.getLogger("pack")

# ---------------------------------------------------------------------------
# State providers — injected into routes via Depends()
# ---------------------------------------------------------------------------


def get_repo(request: Request) -> Repo:
    return request.app.state.repo


def get_registry(request: Request) -> HuntRegistry:
    return request.app.state.registry


def get_client(request: Request) -> QwenClient:
    return request.app.state.client


def get_bus(request: Request) -> EventBus:
    return request.app.state.bus


def get_pool(request: Request):
    return request.app.state.pool


def get_background(request: Request) -> set[asyncio.Task]:
    return request.app.state.background


# ---------------------------------------------------------------------------
# Shared utilities used by multiple routers
# ---------------------------------------------------------------------------


def _accepted(body: dict):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=body)


async def _read_capped(file: UploadFile) -> bytes:
    """Read an upload fully but refuse anything over `max_upload_mb` BEFORE buffering it all —
    an unbounded `await file.read()` lets one client OOM the engine."""
    cap = settings.max_upload_mb * 1024 * 1024
    if file.size is not None and file.size > cap:
        raise HTTPException(
            status_code=413, detail=f"file too large (max {settings.max_upload_mb}MB)"
        )
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1 << 20):  # 1 MiB at a time
        total += len(chunk)
        if total > cap:
            raise HTTPException(
                status_code=413, detail=f"file too large (max {settings.max_upload_mb}MB)"
            )
        chunks.append(chunk)
    return b"".join(chunks)
