"""The doors in — REST API surface (Doc 04 §6).

Commands return **202 Accepted**. The truth arrives on the **stream**: a command nudges the
running Supervisor, which emits the resulting events (in correct seq order) through the one
Emitter. The live event stream itself (WS /hunts/:id/stream) is served by the Rust GATEWAY,
which tails Redis — never this service.

Lifecycle: on startup we open the asyncpg pool, apply the schema, wire the shared event bus,
hunt registry, model client, and start the outbox relay (Postgres → Redis). On shutdown we
cancel running hunts, drain the relay, and close everything.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.bus.redis_stream import EventBus
from app.config import settings
from app.db.pool import apply_schema, create_pool
from app.db.repo import Repo
from app.engine.core import Emitter
from app.engine.ids import new_hunt_id, new_instinct_id
from app.engine.registry import HuntRegistry
from app.engine.relay import OutboxRelay
from app.engine.supervisor import Supervisor
from app.qwen.client import QwenClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await create_pool()
    await apply_schema(pool)
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

    try:
        yield
    finally:
        await registry.shutdown()
        await relay.stop()
        await bus.close()
        await pool.close()


app = FastAPI(
    title="Pack Engine",
    version="0.1.0",
    description=(
        "The Python brain. All REST commands and all writes (Doc 04 §2).\n\n"
        "**Commands return 202.** The result is not in the HTTP response — it lands on the "
        "event stream as the running hunt acts. Connect a WebSocket to the gateway at "
        "`/hunts/{hunt_id}/stream?from_seq=0` to watch the hunt unfold."
    ),
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "hunts",
            "description": "Create and drive a hunt. Commands are 202; truth is on the stream.",
        },
        {"name": "instincts", "description": "Saved plan presets (the Den)."},
        {"name": "system", "description": "Health and meta."},
    ],
)


# --- helpers ---------------------------------------------------------------------------


def _repo(request: Request) -> Repo:
    return request.app.state.repo


def _registry(request: Request) -> HuntRegistry:
    return request.app.state.registry


def _accepted(body: dict) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=body)


# --- command + response bodies ---------------------------------------------------------


class CreateHunt(BaseModel):
    input: str | None = Field(None, description="The task, typed or transcribed.")
    instinct_id: str | None = Field(None, description="Start from a saved instinct instead.")
    source: str = Field("typed", description="typed | spoken | dropped")


class ApprovePlan(BaseModel):
    mode: str = Field(..., description="wild | on_signal | on_command")
    boundary_usd: float = Field(..., description="The dollar Boundary for this hunt.")
    edits: dict | None = None


class ResolveHold(BaseModel):
    resolution: str
    edited_text: str | None = None


class ResumeHunt(BaseModel):
    boundary_usd: float


class SaveInstinct(BaseModel):
    label: str
    spec: dict = Field(default_factory=dict)


class HuntCreated(BaseModel):
    hunt_id: str
    state: str


class HuntSnapshot(BaseModel):
    hunt_id: str
    state: str
    last_seq: int


class CommandAccepted(BaseModel):
    hunt_id: str
    accepted: bool


# --- system ----------------------------------------------------------------------------


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "pack-engine"}


# --- hunts -----------------------------------------------------------------------------


@app.post("/hunts", status_code=202, response_model=HuntCreated, tags=["hunts"])
async def create_hunt(body: CreateHunt, request: Request) -> JSONResponse:
    """Open a hunt. Returns 202 with the new hunt_id; the Supervisor starts planning at once.

    Watch `hunt_created` → `plan_proposed` arrive on the stream, then POST `/plan/approve`.
    """
    repo, registry = _repo(request), _registry(request)
    hunt_id = new_hunt_id()
    await repo.create_hunt(hunt_id, body.source, body.input)

    handle = registry.register(hunt_id)
    emitter = Emitter(hunt_id, repo)
    supervisor = Supervisor(
        hunt_id,
        emitter,
        repo,
        request.app.state.client,
        handle.commands,
        source=body.source,
        raw_input=body.input or "",
    )
    handle.task = asyncio.create_task(supervisor.run(), name=f"hunt-{hunt_id}")
    return _accepted({"hunt_id": hunt_id, "state": "planning"})


@app.get("/hunts", tags=["hunts"])
async def list_hunts(request: Request) -> dict:
    """Recent hunts, newest first — the Den's Past Hunts list."""
    return {"hunts": await _repo(request).list_hunts()}


@app.get("/hunts/{hunt_id}", response_model=HuntSnapshot, tags=["hunts"])
async def get_hunt(hunt_id: str, request: Request) -> JSONResponse:
    """Snapshot: state plus last_seq (for reconnect/replay). 404 if the hunt is unknown."""
    snap = await _repo(request).get_hunt_snapshot(hunt_id)
    if snap is None:
        return JSONResponse(status_code=404, content={"detail": "hunt not found"})
    return JSONResponse(
        content={"hunt_id": snap["hunt_id"], "state": snap["state"], "last_seq": snap["last_seq"]}
    )


@app.post(
    "/hunts/{hunt_id}/plan/approve", status_code=202, response_model=CommandAccepted, tags=["hunts"]
)
async def approve_plan(hunt_id: str, body: ApprovePlan, request: Request) -> JSONResponse:
    """Approve the plan and set the Boundary. The hunt begins; events flow on the stream."""
    ok = await _registry(request).send(
        hunt_id,
        {
            "type": "approve_plan",
            "mode": body.mode,
            "boundary_usd": body.boundary_usd,
            "edits": body.edits,
        },
    )
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "hunt not running here"})
    return _accepted({"hunt_id": hunt_id, "accepted": True})


@app.post(
    "/hunts/{hunt_id}/inputs", status_code=202, response_model=CommandAccepted, tags=["hunts"]
)
async def add_input(hunt_id: str, request: Request) -> JSONResponse:
    """The mid-hunt upload. The pack absorbs new input without restarting (handling NEXT)."""
    ok = await _registry(request).send(hunt_id, {"type": "add_input"})
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "hunt not running here"})
    return _accepted({"hunt_id": hunt_id, "accepted": True})


@app.post(
    "/hunts/{hunt_id}/holds/{hold_id}/resolve",
    status_code=202,
    response_model=CommandAccepted,
    tags=["hunts"],
)
async def resolve_hold(
    hunt_id: str, hold_id: str, body: ResolveHold, request: Request
) -> JSONResponse:
    """Answer an open Hold. The hunt resumes from where it paused."""
    ok = await _registry(request).send(
        hunt_id,
        {
            "type": "resolve_hold",
            "hold_id": hold_id,
            "resolution": body.resolution,
            "edited_text": body.edited_text,
        },
    )
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "hunt not running here"})
    return _accepted({"hunt_id": hunt_id, "hold_id": hold_id, "accepted": True})


@app.post("/hunts/{hunt_id}/stop", status_code=202, response_model=CommandAccepted, tags=["hunts"])
async def stop_hunt(hunt_id: str, request: Request) -> JSONResponse:
    """Stop the hunt. Emits `hunt_stopped` and winds the Supervisor down."""
    ok = await _registry(request).send(hunt_id, {"type": "stop"})
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "hunt not running here"})
    return _accepted({"hunt_id": hunt_id, "accepted": True})


@app.post(
    "/hunts/{hunt_id}/resume", status_code=202, response_model=CommandAccepted, tags=["hunts"]
)
async def resume_hunt(hunt_id: str, _: ResumeHunt) -> JSONResponse:
    """Resume from the latest checkpoint with a new Boundary (resume logic is NEXT)."""
    return _accepted({"hunt_id": hunt_id, "accepted": True})


@app.post(
    "/hunts/{hunt_id}/benchmark", status_code=202, response_model=CommandAccepted, tags=["hunts"]
)
async def benchmark(hunt_id: str) -> JSONResponse:
    """Run the Lone Wolf vs the Pack (NEXT)."""
    return _accepted({"hunt_id": hunt_id, "accepted": True})


@app.get("/hunts/{hunt_id}/tracks/export", tags=["hunts"])
async def export_tracks(hunt_id: str, request: Request) -> dict:
    """Redacted Tracks export — the full event log for a hunt (PII redaction is NEXT)."""
    events = await _repo(request).replay_events(hunt_id, 0)
    return {"hunt_id": hunt_id, "events": [e.model_dump() for e in events], "redacted": False}


@app.get("/hunts/{hunt_id}/artifact", tags=["hunts"])
async def get_artifact(hunt_id: str, request: Request) -> JSONResponse:
    """The hunt's final artifact (Howler's draft) for the reading view. 404 if none yet."""
    artifact = await _repo(request).get_final_artifact(hunt_id)
    if artifact is None:
        return JSONResponse(status_code=404, content={"detail": "no final artifact yet"})
    return JSONResponse(content=artifact)


# --- instincts -------------------------------------------------------------------------


@app.get("/instincts", tags=["instincts"])
async def list_instincts(request: Request) -> dict:
    return {"instincts": await _repo(request).list_instincts()}


@app.post("/instincts", status_code=202, tags=["instincts"])
async def save_instinct(body: SaveInstinct, request: Request) -> JSONResponse:
    instinct_id = new_instinct_id()
    await _repo(request).save_instinct(instinct_id, body.label, body.spec)
    return _accepted({"instinct_id": instinct_id, "accepted": True})


@app.post("/uploads", tags=["system"])
async def signed_upload() -> dict:
    """Signed OSS upload (private objects, signed URLs) — NEXT."""
    return {"upload_url": "https://oss.example/signed", "object_key": "stub"}


# NOTE: WS /hunts/:id/stream?from_seq=n is served by the RUST GATEWAY (gateway/), not here.
