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
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
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
from app.qwen.types import CallSpec


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

# Local dev runs the frontend on :5173 and the engine on :8000 (cross-origin). In prod the
# nginx in deploy/ makes them same-origin, so this is harmless there. No cookies → "*" is fine.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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
    task: str = ""


class AskAlpha(BaseModel):
    question: str


class IntakeBody(BaseModel):
    # The conversation so far: [{"role": "user"|"assistant", "content": "..."}]
    messages: list[dict] = Field(default_factory=list)


# The clarify-gate prompt (research-backed: clarify → confirm → run). Alpha decides if there is a
# real, actionable task yet; otherwise he just talks. Strictly on-voice (Doc 02 §08).
_ALPHA_INTAKE = (
    "You are Alpha, the leader of the Pack, talking with the Packmaster. You're warm, sharp, "
    "plain-spoken, calm and quietly confident, with a light touch of wit. You chat like a "
    "genuinely helpful, intelligent person — a real conversation, never a form.\n"
    "Respond with ONLY a JSON object, no prose around it: "
    '{"reply": string, "ready": boolean, "brief": string}.\n'
    "\n"
    "Writing `reply` (this is what makes you feel smart, not robotic):\n"
    "- Lead with the actual answer, then add only what's genuinely useful — substantive but easy "
    "to read. Say exactly as much as the moment needs: a quick fact is a sentence; a real question "
    "deserves a few. Don't pad, don't ramble, and don't be clipped or curt.\n"
    "- Sound human and present-tense. First person ('I', 'me') is good; a little warmth and "
    "personality is welcome. No jargon, no robotic filler, no repeating 'name a task'.\n"
    "- When you need something from them, end with ONE natural question — never a stack.\n"
    "\n"
    "Launching the Pack (`ready`):\n"
    "- ready=true when they ask you to find, research, look up, gather, compare, write, draft, "
    "review, summarize, analyze, or dig something up — anything needing real work or looking "
    "things up, even if it needs current or web info (the Pack does the looking, so never decline "
    "of data). Then `brief` = one crisp sentence naming the job, and `reply` names what you'll go "
    "do in your own warm words, scoped concretely so they know exactly what's coming.\n"
    '- otherwise ready=false and brief="": greetings, questions about you, general chat, thinking '
    "out loud, or a simple fact you can just answer. Be a good conversationalist.\n"
    "If your reply says you'll go do something now, ready MUST be true.\n"
    "\n"
    "Examples:\n"
    'User: "hi" → {"reply": "Hey — good to see you. I\'m Alpha; I run the Pack, so whatever '
    'you\'re chasing, I can put a team on it. What are you working on?", "ready": false, '
    '"brief": ""}\n'
    'User: "who are you?" → {"reply": "I\'m Alpha, the lead of the Pack — think of me as your '
    "point person. You tell me what you need looked into, written, or sorted out, and I send a "
    'coordinated team after it while you watch it happen. What can I get started on?", '
    '"ready": false, "brief": ""}\n'
    'User: "what is the capital of France?" → {"reply": "Paris — and it\'s been the seat of '
    'French power for centuries. Want me to dig into anything about it?", "ready": false, '
    '"brief": ""}\n'
    'User: "research the BNPL market in Nigeria and write me a brief" → {"reply": "Got it — I\'ll '
    "put the pack on Nigeria's BNPL market: who's leading, what the regulators are doing, and pull "
    'it into a clean brief for you. Ready when you are.", "ready": true, "brief": "Research the '
    'BNPL market in Nigeria — key players and regulation — and write a brief."}'
)

_GREETINGS = {
    "hi",
    "hii",
    "hey",
    "hello",
    "yo",
    "sup",
    "hiya",
    "howdy",
    "ok",
    "okay",
    "thanks",
    "thank you",
    "good morning",
    "good afternoon",
    "good evening",
    "wassup",
    "whatsup",
}


_QUESTION_STARTS = {
    "who", "what", "why", "how", "when", "where", "which", "can",
    "could", "do", "does", "is", "are", "should", "would", "will",
}


def _looks_like_task(text: str) -> bool:
    """Offline heuristic for the clarify-gate when there's no model: greetings, questions, and bare
    fragments aren't tasks; a longer imperative is treated as actionable. (Degraded no-key path —
    the live model does the real judging.)"""
    raw = text.strip()
    t = raw.lower().rstrip("!.?")
    if not t or t in _GREETINGS or raw.endswith("?"):
        return False
    words = t.split()
    if words[0] in _QUESTION_STARTS:
        return False
    return len(words) >= 3


def _last_user(messages: list[dict]) -> str:
    return next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")


def _parse_intake(text: str) -> dict | None:
    """Pull the intake JSON out of the model's reply, tolerating a stray ```fence or prose around
    it. Returns None if there's no usable object — callers MUST NOT launch on a None."""
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[-1]
    for candidate in (text, text[text.find("{") : text.rfind("}") + 1] if "{" in text else ""):
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict) and "ready" in obj:
                return obj
        except json.JSONDecodeError:
            continue
    return None


# Alpha's CHAT voice — deliberately NOT the internal orchestrator prompt (that one is full of
# ledgers/laws/gates and would leak straight into the UI, breaking product voice, Doc 02 §08).
_ALPHA_CHAT = (
    "You are Alpha, leader of the Pack, talking to the Packmaster. Answer in plain English, "
    "present tense, warm and brief — 2 to 4 sentences. Never mention any internal machinery: "
    "no tokens, models, prompts, agents, ledgers, gates, plans-as-lists, or jargon of any kind. "
    "Do not dump checklists or step plans. Just answer the question helpfully and naturally."
)


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
        content={
            "hunt_id": snap["hunt_id"],
            "state": snap["state"],
            "last_seq": snap["last_seq"],
            "task": snap["raw_input"],
        }
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


@app.post("/hunts/intake", tags=["hunts"])
async def intake(body: IntakeBody, request: Request) -> JSONResponse:
    """Front-door clarify-gate: Alpha converses until there's a real task, then signals ready with
    a one-line brief. No hunt is created here — the frontend creates one only when ready=true."""
    client: QwenClient = request.app.state.client
    msgs = [m for m in body.messages if m.get("content")]
    last = _last_user(msgs)

    if client.offline:
        if _looks_like_task(last):
            return JSONResponse(
                {
                    "reply": "On it — I'll get the Pack on that.",
                    "ready": True,
                    "brief": last.strip()[:200],
                }
            )
        return JSONResponse(
            {
                "reply": "I'm Alpha — I lead the Pack. Ask me anything, or tell me what you'd"
                " like looked into, written, or sorted.",
                "ready": False,
                "brief": "",
            }
        )

    result = await client.complete(
        CallSpec(
            hunt_id="intake",
            wolf_id="alpha",
            tier="plus",
            intent="intake",
            messages=[{"role": "system", "content": _ALPHA_INTAKE}, *msgs],
        )
    )
    text = (result.text or "").strip()
    parsed = _parse_intake(text)
    if parsed is not None:
        reply = (
            str(parsed.get("reply") or "").strip() or "Tell me what you want the pack to hunt down."
        )
        ready = bool(parsed.get("ready"))
        brief = str(parsed.get("brief") or "").strip()
    else:
        # No usable JSON — treat the model's words as a normal reply and NEVER launch on a miss.
        reply = text or "Tell me what you want the pack to hunt down."
        ready = False
        brief = ""
    if ready and not brief:
        brief = last.strip()[:200]
    return JSONResponse({"reply": reply, "ready": ready, "brief": brief})


@app.post("/hunts/{hunt_id}/ask", tags=["hunts"])
async def ask_alpha(hunt_id: str, body: AskAlpha, request: Request) -> JSONResponse:
    """A side question to Alpha about the hunt — a one-shot model call (NOT event-sourced).
    Offline this returns FakeQwen's canned reply, so the chat works with no key too."""
    snap = await _repo(request).get_hunt_snapshot(hunt_id)
    task = (snap or {}).get("raw_input", "")
    client: QwenClient = request.app.state.client
    result = await client.complete(
        CallSpec(
            hunt_id=hunt_id,
            wolf_id="alpha",
            tier="plus",
            intent="chat",
            messages=[
                {"role": "system", "content": _ALPHA_CHAT},
                {
                    "role": "user",
                    "content": f"The hunt is about: {task}\n\nThe Packmaster asks: {body.question}",
                },
            ],
        )
    )
    return JSONResponse(content={"reply": result.text})


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
