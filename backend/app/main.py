"""The doors in — REST API surface (Doc 04 §6).

Commands return 202. Truth arrives on the stream. REST is served by THIS Python engine;
the stream endpoint (WS /hunts/:id/stream) is served by the Rust gateway, not here.

This is the scaffold: routes are typed and return 202/stub payloads so the frontend can
wire commands against real shapes today. The engine work (Jun 13-15) fills the bodies.
"""

from __future__ import annotations

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(
    title="Pack Engine",
    version="0.1.0",
    description="The Python brain. All REST commands + all writes (Doc 04 §2).",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "pack-engine"}


# --- Command bodies -------------------------------------------------------------------


class CreateHunt(BaseModel):
    input: str | None = None
    instinct_id: str | None = None
    source: str = "typed"  # typed | spoken | dropped


class ApprovePlan(BaseModel):
    mode: str  # wild | on_signal | on_command
    boundary_usd: float
    edits: dict | None = None


class ResolveHold(BaseModel):
    resolution: str
    edited_text: str | None = None


class ResumeHunt(BaseModel):
    boundary_usd: float


def _accepted(body: dict) -> JSONResponse:
    """Commands return 202; the result lands on the stream."""
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=body)


# --- The surface (Doc 04 §6) ----------------------------------------------------------


@app.post("/hunts")
async def create_hunt(_: CreateHunt) -> JSONResponse:
    """Input or instinct_id in; a hunt in planning state out."""
    return _accepted({"hunt_id": "hunt_stub", "state": "planning"})


@app.get("/hunts/{hunt_id}")
async def get_hunt(hunt_id: str) -> dict:
    """Snapshot: state plus last_seq."""
    return {"hunt_id": hunt_id, "state": "planning", "last_seq": 0}


@app.post("/hunts/{hunt_id}/plan/approve")
async def approve_plan(hunt_id: str, _: ApprovePlan) -> JSONResponse:
    return _accepted({"hunt_id": hunt_id, "accepted": True})


@app.post("/hunts/{hunt_id}/inputs")
async def add_input(hunt_id: str) -> JSONResponse:
    """The mid-hunt upload. The pack absorbs new input without restarting."""
    return _accepted({"hunt_id": hunt_id, "accepted": True})


@app.post("/hunts/{hunt_id}/holds/{hold_id}/resolve")
async def resolve_hold(hunt_id: str, hold_id: str, _: ResolveHold) -> JSONResponse:
    return _accepted({"hunt_id": hunt_id, "hold_id": hold_id, "accepted": True})


@app.post("/hunts/{hunt_id}/stop")
async def stop_hunt(hunt_id: str) -> JSONResponse:
    return _accepted({"hunt_id": hunt_id, "accepted": True})


@app.post("/hunts/{hunt_id}/resume")
async def resume_hunt(hunt_id: str, _: ResumeHunt) -> JSONResponse:
    """Resume with a new boundary, restoring the latest checkpoint."""
    return _accepted({"hunt_id": hunt_id, "accepted": True})


@app.post("/hunts/{hunt_id}/benchmark")
async def benchmark(hunt_id: str) -> JSONResponse:
    """Run the Lone Wolf vs the Pack."""
    return _accepted({"hunt_id": hunt_id, "accepted": True})


@app.get("/hunts/{hunt_id}/tracks/export")
async def export_tracks(hunt_id: str) -> dict:
    """Redacted Tracks export (PII redacted)."""
    return {"hunt_id": hunt_id, "events": [], "redacted": True}


@app.get("/instincts")
async def list_instincts() -> dict:
    return {"instincts": []}


@app.post("/instincts")
async def save_instinct() -> JSONResponse:
    return _accepted({"accepted": True})


@app.post("/uploads")
async def signed_upload() -> dict:
    """Signed OSS upload (private objects, signed URLs)."""
    return {"upload_url": "https://oss.example/signed", "object_key": "stub"}


# NOTE: WS /hunts/:id/stream?from_seq=n is served by the RUST GATEWAY (gateway/), not here.
