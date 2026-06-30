"""Pack Engine — app factory.

Commands return 202 Accepted. Truth arrives on the event stream — connect a WebSocket to the
gateway at /hunts/{hunt_id}/stream?from_seq=0 to watch the hunt unfold.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.bus.redis_stream import EventBus
from app.config import settings
from app.core.middleware import http_exception_handler, request_context, unhandled_exception_handler
from app.db.migrate import run_migrations
from app.db.pool import create_pool
from app.db.repo import Repo
from app.engine.registry import HuntRegistry
from app.engine.relay import OutboxRelay
from app.engine.startup import recover_stranded_hunts
from app.qwen.client import QwenClient
from app.routers import documents, hunts, instincts, memory, projects, system, tools

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await create_pool()
    await run_migrations(pool)
    bus = EventBus(settings.redis_url)
    repo = Repo(pool)
    registry = HuntRegistry()
    relay = OutboxRelay(pool, bus, repo)
    await relay.start()

    app.state.pool = pool
    app.state.bus = bus
    app.state.repo = repo
    app.state.registry = registry
    app.state.relay = relay
    app.state.client = QwenClient()
    app.state.background: set[asyncio.Task] = set()

    await recover_stranded_hunts(app, repo)

    try:
        yield
    finally:
        await registry.shutdown()
        for bg in list(app.state.background):
            bg.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await bg
        await relay.stop()
        await bus.close()
        await pool.close()


app = FastAPI(
    title="Pack Engine",
    version="0.1.0",
    description=(
        "The Python brain. All REST commands and all writes (Doc 04 §2).\n\n"
        "**Commands return 202.** The result is not in the HTTP response — it lands on the "
        "event stream as the running hunt acts."
    ),
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "hunts",
            "description": "Create and drive a hunt. Commands are 202; truth is on the stream.",
        },
        {"name": "projects", "description": "Workspaces that group hunts (the Den)."},
        {"name": "instincts", "description": "Saved plan/formation presets."},
        {"name": "documents", "description": "Your local knowledge base."},
        {"name": "memory", "description": "The Elder's cross-hunt learnings."},
        {"name": "system", "description": "Health, readiness, and meta."},
    ],
)

_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()] or ["*"]
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"])
app.middleware("http")(request_context)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(hunts.router)
app.include_router(projects.router)
app.include_router(instincts.router)
app.include_router(documents.router)
app.include_router(memory.router)
app.include_router(system.router)
app.include_router(tools.router)
