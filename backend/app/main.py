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
import base64
import contextlib
import json
import logging
import re
import secrets
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from openai import APIStatusError, RateLimitError
from pydantic import BaseModel, Field

from app.tools.file_parse import detect_kind, parse_bytes, parse_url
from app.tools.redact import redact_event
from app.tools.vision import describe_image
from app.tools.transcribe import TRANSCRIBER
from app.tools.video import extract_audio

from app.bus.redis_stream import EventBus
from app.config import settings
from app.db.pool import apply_schema, create_pool
from app.db.repo import Repo
from app.events.models import Event
from app.engine.core import Emitter
from app.engine.ids import new_hunt_id, new_instinct_id, new_project_id
from app.engine.benchmark import run_benchmark
from app.engine.registry import HuntRegistry
from app.engine.refine import refine_brief
from app.engine.rehearse import rehearse
from app.engine.relay import OutboxRelay
from app.engine.strategies import strategy_catalog
from app.engine.supervisor import Supervisor

# Keeps fire-and-forget background tasks (benchmarks) referenced so they aren't GC'd mid-run.
_BACKGROUND: set[asyncio.Task] = set()
from app.qwen.client import QwenClient
from app.qwen.types import CallSpec


_RESTART_REASON = "The engine restarted before this hunt could finish — start a new one."


async def _recover_stranded_hunts(app: FastAPI, repo: Repo) -> None:
    """A previous engine stop leaves in-flight hunts with no Supervisor (state lived in-process). On
    startup: a hunt that was paused at the Boundary (`halted_boundary`) is RE-REGISTERED and resumed
    (B11) — it rebuilds from the event log and waits for the Packmaster's /resume. A hunt that died
    mid-flight can't resume a linear coroutine, so it's closed with an honest `hunt_failed`. Best-
    effort — never blocks startup; a bad row is skipped."""
    log = logging.getLogger("pack")
    try:
        stranded = await repo.list_unfinished_hunts()
    except Exception:  # noqa: BLE001 — recovery is best-effort; don't hold up serving
        log.exception("stranded-hunt recovery failed to list; skipping")
        return
    registry: HuntRegistry = app.state.registry
    for h in stranded:
        hid = h["hunt_id"]
        try:
            if h.get("state") == "halted_boundary":  # resumable — re-register and wait for /resume
                handle = registry.register(hid)
                sup = Supervisor(hid, Emitter(hid, repo), repo, app.state.client, handle.commands)
                handle.task = asyncio.create_task(sup.resume_run(), name=f"resume-{hid}")
                log.info("re-registered halted hunt %s for resume", hid)
                continue
            seq = (await repo.get_last_seq(hid)) + 1
            await repo.append_event(
                Event(
                    hunt_id=hid,
                    seq=seq,
                    type="hunt_failed",
                    actor="engine",
                    payload={"reason": "engine_restarted", "reason_plain_english": _RESTART_REASON},
                )
            )
            await repo.set_hunt_state(hid, "failed")
        except Exception:  # noqa: BLE001 — skip a bad hunt, keep reconciling the rest
            log.warning("could not reconcile stranded hunt %s", hid)
            continue


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

    await _recover_stranded_hunts(app, repo)  # after state is wired (resume re-registers hunts)

    try:
        yield
    finally:
        await registry.shutdown()  # cancel in-flight hunt Supervisors
        for bg in list(_BACKGROUND):  # cancel tracked fire-and-forget tasks (benchmarks)
            bg.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await bg
        await relay.stop()  # final drain so nothing is stranded, then release the listener
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

# --- observability + a consistent error envelope --------------------------------------

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s"
)
logger = logging.getLogger("pack")


@app.middleware("http")
async def _request_context(request: Request, call_next):
    """Stamp every request with a short id (logged + returned as X-Request-ID) for tracing."""
    rid = secrets.token_hex(4)
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    logger.info("[%s] %s %s -> %s", rid, request.method, request.url.path, response.status_code)
    return response


@app.exception_handler(StarletteHTTPException)
async def _http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    rid = getattr(request.state, "request_id", "?")
    return JSONResponse(
        status_code=exc.status_code, content={"detail": exc.detail, "request_id": rid}
    )


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    rid = getattr(request.state, "request_id", "?")
    logger.exception("[%s] unhandled error on %s %s", rid, request.method, request.url.path)
    return JSONResponse(
        status_code=500, content={"detail": "internal server error", "request_id": rid}
    )


# --- helpers ---------------------------------------------------------------------------


def _repo(request: Request) -> Repo:
    return request.app.state.repo


def _registry(request: Request) -> HuntRegistry:
    return request.app.state.registry


def _accepted(body: dict) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=body)


async def _read_capped(file: UploadFile) -> bytes:
    """Read an upload fully, but refuse anything over `max_upload_mb` BEFORE buffering it all — an
    unbounded `await file.read()` lets one client OOM the engine."""
    cap = settings.max_upload_mb * 1024 * 1024
    if file.size is not None and file.size > cap:
        raise HTTPException(status_code=413, detail=f"file too large (max {settings.max_upload_mb}MB)")
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


# --- command + response bodies ---------------------------------------------------------


# Shared enums — reject junk at the door (422) instead of letting it reach the engine.
Strategy = Literal["orchestrate", "deep_dive", "critique"]
Source = Literal["typed", "spoken", "dropped"]
Mode = Literal["wild", "on_signal", "on_command"]
InputKind = Literal["text", "pdf", "csv", "md", "url", "image", "audio", "video"]
_MAX_TASK = 10_000
_MAX_INPUT = 200_000


class CreateHunt(BaseModel):
    input: str | None = Field(None, max_length=_MAX_TASK, description="The task, typed or transcribed.")
    instinct_id: str | None = Field(None, max_length=120)
    source: Source = "typed"
    strategy: Strategy | None = Field(None, description="Research strategy.")
    team: list[dict] | None = Field(None, max_length=16, description="Seed formation [{role,count}].")


class ApprovePlan(BaseModel):
    mode: Mode
    boundary_usd: float = Field(..., ge=0, le=1000, description="The dollar Boundary for this hunt.")
    edits: dict | None = None


class ResolveHold(BaseModel):
    resolution: str = Field(..., max_length=2000)
    edited_text: str | None = Field(None, max_length=_MAX_INPUT)


class ResumeHunt(BaseModel):
    boundary_usd: float = Field(..., ge=0, le=1000)


class SaveInstinct(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    spec: dict = Field(default_factory=dict)


class HuntCreated(BaseModel):
    hunt_id: str
    state: str


class HuntSnapshot(BaseModel):
    hunt_id: str
    state: str
    last_seq: int
    task: str = ""
    strategy: str = "orchestrate"


class AskAlpha(BaseModel):
    # Multi-turn: the conversation so far [{"role": "user"|"assistant", "content": "..."}].
    # `question` is the back-compat single-turn fallback.
    question: str | None = Field(None, max_length=_MAX_TASK)
    messages: list[dict] = Field(default_factory=list, max_length=200)


class IntakeBody(BaseModel):
    # The conversation so far: [{"role": "user"|"assistant", "content": "..."}]
    messages: list[dict] = Field(default_factory=list, max_length=200)


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
    "- Format for easy reading. When the answer is a set of items, options, or steps, use a short "
    "Markdown bullet list ('- ' lines) with the key term in **bold**; otherwise write natural "
    "prose. Leave a blank line between distinct ideas. Keep it conversational, not a wall.\n"
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
            # strict=False: models routinely put real newlines inside the string values, which
            # the default parser rejects — that miss used to dump the raw JSON into the chat.
            obj = json.loads(candidate, strict=False)
            if isinstance(obj, dict) and "ready" in obj:
                return obj
        except json.JSONDecodeError:
            continue
    return None


def _safe_reply(text: str) -> str:
    """A reply for when intake JSON can't be parsed — never leak raw braces into the chat."""
    if text.strip().startswith("{") or '"reply"' in text:
        m = re.search(r'"reply"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if m:
            try:
                return json.loads(f'"{m.group(1)}"')
            except json.JSONDecodeError:
                pass
        return "Tell me what you want the pack to hunt down."
    return text or "Tell me what you want the pack to hunt down."


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


@app.get("/strategies", tags=["system"])
async def strategies() -> dict:
    """The selectable research strategies (the Door's mode picker)."""
    return {"strategies": strategy_catalog(), "default": settings.default_strategy}


# --- hunts -----------------------------------------------------------------------------


@app.post("/hunts", status_code=202, response_model=HuntCreated, tags=["hunts"])
async def create_hunt(body: CreateHunt, request: Request) -> JSONResponse:
    """Open a hunt. Returns 202 with the new hunt_id; the Supervisor starts planning at once.

    Watch `hunt_created` → `plan_proposed` arrive on the stream, then POST `/plan/approve`.
    """
    repo, registry = _repo(request), _registry(request)
    hunt_id = new_hunt_id()
    strategy = body.strategy or settings.default_strategy
    raw_input = body.input or ""
    seed_team: list[dict] | None = body.team if body.team else None  # v5.2: a Library formation

    # Start from a saved instinct (the Den) when one is given: its spec seeds the task + strategy,
    # and — v5.1 — its saved formation (team) if it has one.
    if body.instinct_id:
        inst = await repo.get_instinct(body.instinct_id)
        if inst is not None:
            spec = inst.get("spec") or {}
            raw_input = body.input or str(spec.get("task") or inst.get("label") or "").strip()
            strategy = body.strategy or str(spec.get("strategy") or strategy)
            team = spec.get("team")
            if isinstance(team, list) and team:
                seed_team = team

    await repo.create_hunt(hunt_id, body.source, raw_input, strategy)

    handle = registry.register(hunt_id)
    emitter = Emitter(hunt_id, repo)
    supervisor = Supervisor(
        hunt_id,
        emitter,
        repo,
        request.app.state.client,
        handle.commands,
        source=body.source,
        raw_input=raw_input,
        strategy=strategy,
        seed_team=seed_team,
    )
    handle.task = asyncio.create_task(supervisor.run(), name=f"hunt-{hunt_id}")
    return _accepted({"hunt_id": hunt_id, "state": "planning"})


@app.get("/hunts", tags=["hunts"])
async def list_hunts(
    request: Request, project_id: str | None = None, cursor: str | None = None, limit: int = 50
) -> dict:
    """Recent hunts, newest first — the Den's Past Hunts list. Optionally scoped to a project.
    Cursor pagination: pass the returned `next_cursor` to page older (null when no more)."""
    lim = max(1, min(limit, 100))
    hunts = await _repo(request).list_hunts(limit=lim + 1, project_id=project_id, cursor=cursor)
    has_more = len(hunts) > lim
    hunts = hunts[:lim]
    next_cursor = hunts[-1]["created_at"] if (has_more and hunts) else None
    return {"hunts": hunts, "next_cursor": next_cursor}


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
            "strategy": snap.get("strategy", "orchestrate"),
        }
    )


class HuntPatch(BaseModel):
    title: str | None = Field(None, max_length=200)
    archived: bool | None = None
    project_id: str | None = None  # set to a project, or null to unassign (presence checked)


class MessageIn(BaseModel):
    role: Literal["user", "alpha"]
    content: str = Field(..., max_length=_MAX_INPUT)


@app.patch("/hunts/{hunt_id}", tags=["hunts"])
async def patch_hunt(hunt_id: str, body: HuntPatch, request: Request) -> JSONResponse:
    """Rename or archive a hunt (Den history management)."""
    repo = _repo(request)
    if body.title is not None:
        await repo.rename_hunt(hunt_id, body.title.strip()[:120])
    if body.archived is not None:
        await repo.set_archived(hunt_id, body.archived)
    if "project_id" in body.model_fields_set:  # presence, so null explicitly unassigns
        await repo.assign_hunt(hunt_id, body.project_id)
    return JSONResponse({"hunt_id": hunt_id, "ok": True})


@app.delete("/hunts/{hunt_id}", tags=["hunts"])
async def delete_hunt_route(hunt_id: str, request: Request) -> JSONResponse:
    """Delete a hunt and everything hanging off it."""
    await _repo(request).delete_hunt(hunt_id)
    return JSONResponse({"hunt_id": hunt_id, "deleted": True})


# --- projects (workspaces) -------------------------------------------------------------


class ProjectIn(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    instructions: str | None = Field(None, max_length=10_000)


class ProjectPatch(BaseModel):
    label: str | None = Field(None, max_length=200)
    instructions: str | None = Field(None, max_length=10_000)


@app.get("/projects", tags=["projects"])
async def list_projects(request: Request) -> dict:
    """All projects with their (non-archived) hunt counts — powers the Den's project switcher."""
    return {"projects": await _repo(request).list_projects()}


@app.get("/projects/{project_id}", tags=["projects"])
async def get_project_route(project_id: str, request: Request) -> JSONResponse:
    proj = await _repo(request).get_project(project_id)
    if proj is None:
        return JSONResponse(status_code=404, content={"detail": "project not found"})
    return JSONResponse(content=proj)


@app.post("/projects", status_code=202, tags=["projects"])
async def create_project(body: ProjectIn, request: Request) -> JSONResponse:
    pid = new_project_id()
    label = body.label.strip()[:120] or "Untitled project"
    await _repo(request).create_project(pid, label, (body.instructions or "").strip() or None)
    return JSONResponse(status_code=202, content={"project_id": pid, "label": label})


@app.patch("/projects/{project_id}", tags=["projects"])
async def patch_project(project_id: str, body: ProjectPatch, request: Request) -> JSONResponse:
    await _repo(request).update_project(
        project_id,
        body.label.strip()[:120] if body.label else None,
        body.instructions,
    )
    return JSONResponse({"project_id": project_id, "ok": True})


@app.delete("/projects/{project_id}", tags=["projects"])
async def delete_project_route(project_id: str, request: Request) -> JSONResponse:
    """Drop the project; its hunts survive (just unassigned)."""
    await _repo(request).delete_project(project_id)
    return JSONResponse({"project_id": project_id, "deleted": True})


@app.get("/hunts/{hunt_id}/messages", tags=["hunts"])
async def get_messages(hunt_id: str, request: Request) -> dict:
    """The saved Alpha conversation for a hunt (durable, cross-device)."""
    return {"messages": await _repo(request).list_messages(hunt_id)}


@app.post("/hunts/{hunt_id}/messages", status_code=202, tags=["hunts"])
async def post_message(hunt_id: str, body: MessageIn, request: Request) -> JSONResponse:
    """Append one conversation turn to a hunt's durable chat."""
    await _repo(request).save_message(hunt_id, body.role, body.content)
    return JSONResponse(status_code=202, content={"ok": True})


@app.post("/hunts/{hunt_id}/share", tags=["hunts"])
async def share_hunt(hunt_id: str, request: Request) -> JSONResponse:
    """Mint (or reuse) a public read-only token for this hunt's brief."""
    token = secrets.token_urlsafe(9)
    await _repo(request).set_share_token(hunt_id, token)
    return JSONResponse({"token": token})


@app.get("/share/{token}", tags=["hunts"])
async def get_share(token: str, request: Request) -> JSONResponse:
    """Public read-only view of a shared brief (no hunt id, no chat)."""
    data = await _repo(request).get_shared(token)
    if data is None:
        return JSONResponse(status_code=404, content={"detail": "not found"})
    return JSONResponse(content=data)


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


class RehearseBody(BaseModel):
    team: list[dict] | None = None
    strategy: str | None = None


@app.post("/hunts/{hunt_id}/rehearse", tags=["hunts"])
async def rehearse_hunt(hunt_id: str, body: RehearseBody) -> dict:
    """Shadow Hunt (safety rail): estimate this team's cost + time before the pack runs. No spend,
    no events — a pure rehearsal the Plan shows so the Packmaster sees the cost first."""
    strategy = body.strategy or settings.default_strategy
    team = body.team or [{"role": "scout", "count": 3}]
    return rehearse(team, strategy)


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

    try:
        result = await client.complete(
            CallSpec(
                hunt_id="intake",
                wolf_id="alpha",
                tier="plus",
                intent="intake",
                messages=[{"role": "system", "content": _ALPHA_INTAKE}, *msgs],
            )
        )
    except RateLimitError as exc:
        raise HTTPException(429, detail="rate_limit") from exc
    except APIStatusError as e:
        if "content_filter" in str(e):
            raise HTTPException(400, detail="content_filter") from e
        raise HTTPException(500, detail=str(e)) from e
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
        reply = _safe_reply(text)
        ready = False
        brief = ""
    if ready and not brief:
        brief = last.strip()[:200]
    return JSONResponse({"reply": reply, "ready": ready, "brief": brief})


@app.post("/hunts/{hunt_id}/ask", tags=["hunts"])
async def ask_alpha(hunt_id: str, body: AskAlpha, request: Request) -> JSONResponse:
    """A side conversation with Alpha about the hunt — a model call that carries the FULL
    conversation history, so Alpha actually remembers what you've been talking about (NOT
    event-sourced). Offline this returns FakeQwen's canned reply, so the chat works with no key."""
    snap = await _repo(request).get_hunt_snapshot(hunt_id)
    task = (snap or {}).get("raw_input", "")
    client: QwenClient = request.app.state.client

    history = [m for m in body.messages if m.get("content")]
    if not history and body.question:
        history = [{"role": "user", "content": body.question}]

    system = f"{_ALPHA_CHAT}\n\nThe hunt you're discussing is about: {task or 'the current task'}."
    try:
        result = await client.complete(
            CallSpec(
                hunt_id=hunt_id,
                wolf_id="alpha",
                tier="plus",
                intent="chat",
                messages=[{"role": "system", "content": system}, *history],
            )
        )
    except RateLimitError as exc:
        raise HTTPException(429, detail="rate_limit") from exc
    except APIStatusError as e:
        if "content_filter" in str(e):
            raise HTTPException(400, detail="content_filter") from e
        raise HTTPException(500, detail=str(e)) from e
    return JSONResponse(content={"reply": result.text})


_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


async def _stream_tokens(queue: asyncio.Queue, request: Request):
    """Yield SSE `token` frames from the queue until the None sentinel, sending a ~15s heartbeat
    comment during quiet stretches and stopping early if the client has disconnected (so a slow
    upstream + a vanished client can't pin a task forever). The caller cancels the producer."""
    while True:
        try:
            delta = await asyncio.wait_for(queue.get(), timeout=15.0)
        except TimeoutError:
            if await request.is_disconnected():
                return
            yield ": keep-alive\n\n"
            continue
        if delta is None:
            return
        yield f"data: {json.dumps({'type': 'token', 'text': delta})}\n\n"


@app.post("/hunts/intake/stream", tags=["hunts"])
async def intake_stream(body: IntakeBody, request: Request) -> StreamingResponse:
    """SSE variant of /intake — yields `token` events as text arrives, then a `done` event
    with the fully-parsed {reply, ready, brief} payload. The frontend streams the reply live
    and only reacts to readiness on the done event."""
    client: QwenClient = request.app.state.client
    msgs = [m for m in body.messages if m.get("content")]
    last = _last_user(msgs)

    if client.offline:
        if _looks_like_task(last):
            reply, ready, brief = "On it — I'll get the Pack on that.", True, last.strip()[:200]
        else:
            reply, ready, brief = (
                "I'm Alpha — I lead the Pack. Ask me anything, or tell me what you'd like looked into.",
                False, "",
            )
        async def _offline_gen():
            yield f"data: {json.dumps({'type': 'token', 'text': reply})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'reply': reply, 'ready': ready, 'brief': brief})}\n\n"
        return StreamingResponse(_offline_gen(), media_type="text/event-stream", headers=_SSE_HEADERS)

    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _on_delta(delta: str) -> None:
        await queue.put(delta)

    async def _gen():
        async def _run():
            r = await client.complete(
                CallSpec(
                    hunt_id="intake", wolf_id="alpha", tier="plus", intent="intake",
                    force_stream=True,
                    messages=[{"role": "system", "content": _ALPHA_INTAKE}, *msgs],
                ),
                on_delta=_on_delta,
            )
            await queue.put(None)  # sentinel
            return r

        task = asyncio.create_task(_run())
        try:
            async for frame in _stream_tokens(queue, request):
                yield frame
            if await request.is_disconnected():
                return  # client went away; the finally cancels the upstream call

            try:
                result = await task
            except RateLimitError:
                yield f"data: {json.dumps({'type': 'error', 'kind': 'rate_limit'})}\n\n"
                return
            except APIStatusError as e:
                kind = "content_filter" if "content_filter" in str(e) else "unknown"
                yield f"data: {json.dumps({'type': 'error', 'kind': kind})}\n\n"
                return
            text = (result.text or "").strip()
            parsed = _parse_intake(text)
            if parsed is not None:
                reply = str(parsed.get("reply") or "").strip() or "Tell me what you want the pack."
                ready = bool(parsed.get("ready"))
                brief = str(parsed.get("brief") or "").strip()
            else:
                reply, ready, brief = _safe_reply(text), False, ""
            if ready and not brief:
                brief = last.strip()[:200]
            done = {"type": "done", "reply": reply, "ready": ready, "brief": brief}
            yield f"data: {json.dumps(done)}\n\n"
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task

    return StreamingResponse(_gen(), media_type="text/event-stream", headers=_SSE_HEADERS)


@app.post("/hunts/{hunt_id}/ask/stream", tags=["hunts"])
async def ask_stream(hunt_id: str, body: AskAlpha, request: Request) -> StreamingResponse:
    """SSE variant of /ask — yields `token` events then a `done` event with the full reply."""
    snap = await _repo(request).get_hunt_snapshot(hunt_id)
    task_desc = (snap or {}).get("raw_input", "")
    client: QwenClient = request.app.state.client

    history = [m for m in body.messages if m.get("content")]
    if not history and body.question:
        history = [{"role": "user", "content": body.question}]

    system = f"{_ALPHA_CHAT}\n\nThe hunt you're discussing is about: {task_desc or 'the current task'}."
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _on_delta(delta: str) -> None:
        await queue.put(delta)

    async def _gen():
        async def _run():
            r = await client.complete(
                CallSpec(
                    hunt_id=hunt_id, wolf_id="alpha", tier="plus", intent="chat",
                    force_stream=True,
                    messages=[{"role": "system", "content": system}, *history],
                ),
                on_delta=_on_delta,
            )
            await queue.put(None)
            return r

        task = asyncio.create_task(_run())
        try:
            async for frame in _stream_tokens(queue, request):
                yield frame
            if await request.is_disconnected():
                return
            try:
                result = await task
            except RateLimitError:
                yield f"data: {json.dumps({'type': 'error', 'kind': 'rate_limit'})}\n\n"
                return
            except APIStatusError as e:
                kind = "content_filter" if "content_filter" in str(e) else "unknown"
                yield f"data: {json.dumps({'type': 'error', 'kind': kind})}\n\n"
                return
            yield f"data: {json.dumps({'type': 'done', 'reply': result.text})}\n\n"
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task

    return StreamingResponse(_gen(), media_type="text/event-stream", headers=_SSE_HEADERS)


class FeedbackBody(BaseModel):
    turn_index: int
    vote: str = Field(..., pattern="^(up|down)$")


@app.post("/hunts/{hunt_id}/feedback", tags=["hunts"])
async def submit_feedback(hunt_id: str, body: FeedbackBody, request: Request) -> JSONResponse:
    """Record a thumbs-up or thumbs-down vote for one Alpha turn. Fire-and-forget from the UI."""
    await _repo(request).save_feedback(hunt_id, body.turn_index, body.vote)
    return JSONResponse({"ok": True})


@app.get("/hunts/{hunt_id}/feedback", tags=["hunts"])
async def get_feedback(hunt_id: str, request: Request) -> dict:
    """The votes recorded on a hunt's Alpha turns + up/down tallies (previously write-only)."""
    return await _repo(request).feedback_for_hunt(hunt_id)


class AddInput(BaseModel):
    text: str = Field(..., max_length=_MAX_INPUT, description="Text to fold into the hunt.")
    kind: InputKind = "text"


@app.post(
    "/hunts/{hunt_id}/inputs", status_code=202, response_model=CommandAccepted, tags=["hunts"]
)
async def add_input(hunt_id: str, body: AddInput, request: Request) -> JSONResponse:
    """Mid-hunt input. The pack absorbs it at the next synthesis step without restarting: the
    Supervisor persists it, emits `input_added`, and weighs it in the merge/draft."""
    ok = await _registry(request).send(
        hunt_id, {"type": "add_input", "text": body.text, "kind": body.kind}
    )
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
async def resume_hunt(hunt_id: str, body: ResumeHunt, request: Request) -> JSONResponse:
    """Resume a Boundary-halted hunt by raising the Boundary. The paused Supervisor lifts the cap
    and continues from exactly where it stopped (the call it was about to make)."""
    ok = await _registry(request).send(
        hunt_id, {"type": "resume", "boundary_usd": body.boundary_usd}
    )
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "hunt not running here"})
    return _accepted({"hunt_id": hunt_id, "accepted": True})


@app.post(
    "/hunts/{hunt_id}/benchmark", status_code=202, response_model=CommandAccepted, tags=["hunts"]
)
async def benchmark(hunt_id: str, request: Request) -> JSONResponse:
    """Run the Lone Wolf vs the Pack. Launches a background scorer that runs the task single-agent
    and emits benchmark_started → benchmark_completed (with the Scorecard) on the hunt's stream."""
    repo = _repo(request)
    snap = await repo.get_hunt_snapshot(hunt_id)
    if snap is None:
        return JSONResponse(status_code=404, content={"detail": "hunt not found"})
    emitter = Emitter(hunt_id, repo)
    task = snap.get("raw_input", "") or "the task"
    coro = run_benchmark(hunt_id, emitter, repo, request.app.state.client, task)
    task_obj = asyncio.create_task(coro, name=f"benchmark-{hunt_id}")
    _BACKGROUND.add(task_obj)
    task_obj.add_done_callback(_BACKGROUND.discard)
    return _accepted({"hunt_id": hunt_id, "accepted": True})


@app.get("/hunts/{hunt_id}/scorecard", tags=["hunts"])
async def get_scorecard(hunt_id: str, request: Request) -> JSONResponse:
    """The latest benchmark Scorecard for a hunt (Lone Wolf vs Pack), or 404 if none yet."""
    events = await _repo(request).replay_events(hunt_id, 0)
    for e in reversed(events):
        if e.type == "benchmark_completed":
            return JSONResponse(content={"hunt_id": hunt_id, "scorecard": e.payload["scorecard"]})
    return JSONResponse(status_code=404, content={"detail": "no benchmark yet"})


@app.get("/hunts/{hunt_id}/tracks/export", tags=["hunts"])
async def export_tracks(hunt_id: str, request: Request) -> dict:
    """Redacted Tracks export — the full event log for a hunt, with PII masked in every payload
    (emails, phone numbers, card-like digit runs, secret tokens)."""
    events = await _repo(request).replay_events(hunt_id, 0)
    redacted = [redact_event(e.model_dump()) for e in events]
    return {"hunt_id": hunt_id, "events": redacted, "redacted": True}


@app.get("/hunts/{hunt_id}/artifact", tags=["hunts"])
async def get_artifact(hunt_id: str, request: Request) -> JSONResponse:
    """The hunt's final artifact (Howler's draft) for the reading view. 404 if none yet."""
    artifact = await _repo(request).get_final_artifact(hunt_id)
    if artifact is None:
        return JSONResponse(status_code=404, content={"detail": "no final artifact yet"})
    return JSONResponse(content=artifact)


class RefineBody(BaseModel):
    instruction: str = Field("", max_length=2000, description="How to re-angle/tighten the brief.")


@app.post("/hunts/{hunt_id}/refine", status_code=202, tags=["hunts"])
async def refine_hunt(hunt_id: str, body: RefineBody, request: Request) -> JSONResponse:
    """Re-draft + re-forge the brief from its existing claims/sources (no re-scout). The new files
    land on the event stream; the Reward refreshes. 404 if there's no brief, 400 if it had no sources."""
    art = await _repo(request).get_final_artifact(hunt_id)
    if art is None:
        return JSONResponse(status_code=404, content={"detail": "no brief to refine yet"})
    artifact_id = await refine_brief(_repo(request), request.app.state.client, hunt_id, body.instruction)
    if artifact_id is None:
        return JSONResponse(status_code=400, content={"detail": "this brief has no sources to refine"})
    return _accepted({"hunt_id": hunt_id, "artifact_id": artifact_id, "accepted": True})


_DOWNLOADABLE = {"md", "html", "pdf", "docx", "xlsx", "pptx", "png"}


@app.get("/hunts/{hunt_id}/artifacts", tags=["hunts"])
async def list_artifacts(hunt_id: str, request: Request) -> dict:
    """The forged files for this hunt (the Reward's format tabs) — id + kind only."""
    rows = await _repo(request).list_artifacts(hunt_id)
    return {"artifacts": [r for r in rows if r["kind"] in _DOWNLOADABLE]}


@app.get("/hunts/{hunt_id}/artifacts/{artifact_id}", tags=["hunts"])
async def download_artifact(hunt_id: str, artifact_id: str, request: Request) -> Response:
    """Download one forged file — base64-decoded, with the right content-type and a filename."""
    row = await _repo(request).get_artifact_row(artifact_id)
    if row is None or row["hunt_id"] != hunt_id:
        return JSONResponse(status_code=404, content={"detail": "artifact not found"})
    content = row.get("content") or {}
    b64 = content.get("b64")
    if not b64:
        return JSONResponse(status_code=404, content={"detail": "not a downloadable file"})
    data = base64.b64decode(b64)
    mime = content.get("mime", "application/octet-stream")
    filename = f"pack-brief.{row['kind']}"
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- memory (the Elder's cross-hunt notes) ---------------------------------------------


@app.get("/memory", tags=["memory"])
async def get_memory(request: Request) -> dict:
    """What the pack remembers across hunts (the Elder's takeaways), most recent first."""
    rows = await _repo(request).recent_memory(10)
    return {
        "memory": [
            {"text": str(r.get("text") or ""), "hunt_id": r.get("hunt_id")}
            for r in rows
            if str(r.get("text") or "").strip()
        ]
    }


@app.delete("/memory", tags=["memory"])
async def clear_memory_route(request: Request) -> JSONResponse:
    """Forget everything the pack learned (wired to Settings → Clear all saved data)."""
    await _repo(request).clear_memory()
    return JSONResponse({"cleared": True})


# --- spend (v5.4): total cost across hunts ---------------------------------------------


@app.get("/spend", tags=["hunts"])
async def get_spend(request: Request) -> dict:
    """Total spend across all hunts + a per-hunt breakdown, read from each hunt's final totals."""
    items = await _repo(request).spend_summary()
    return {"total_usd": round(sum(i["cost_usd"] for i in items), 4), "hunts": items}


# --- knowledge base (your documents, v4.2) ---------------------------------------------


@app.post("/documents", status_code=202, tags=["documents"])
async def add_document(request: Request, file: UploadFile = File(...)) -> JSONResponse:
    """Add a document to your local knowledge base — parsed to text and researchable by the pack."""
    data = await _read_capped(file)
    kind = detect_kind(file.filename or "", file.content_type or "")
    if kind == "image":
        text = await describe_image(data, file.content_type or "", file.filename or "")
    elif kind == "video":
        return JSONResponse(
            status_code=400, content={"detail": "video can't go in the knowledge base"}
        )
    else:
        text = parse_bytes(data, kind)
    text = (text or "").strip()
    if not text:
        return JSONResponse(
            status_code=400, content={"detail": "couldn't read any text from that file"}
        )
    doc_id = await _repo(request).save_document(file.filename or "document", kind, text)
    return _accepted({"id": doc_id, "name": file.filename, "kind": kind, "chars": len(text)})


@app.get("/documents", tags=["documents"])
async def list_documents_route(request: Request) -> dict:
    """Your knowledge-base documents (metadata only, no full text)."""
    return {"documents": await _repo(request).list_documents()}


@app.get("/documents/{doc_id}", tags=["documents"])
async def get_document_route(doc_id: int, request: Request) -> JSONResponse:
    """One knowledge-base document including its extracted text."""
    doc = await _repo(request).get_document(doc_id)
    if doc is None:
        return JSONResponse(status_code=404, content={"detail": "document not found"})
    return JSONResponse(content=doc)


@app.delete("/documents", tags=["documents"])
async def clear_documents_route(request: Request) -> JSONResponse:
    """Wipe the whole knowledge base (wired to Settings → Clear all saved data)."""
    await _repo(request).clear_documents()
    return JSONResponse({"cleared": True})


@app.delete("/documents/{doc_id}", tags=["documents"])
async def delete_document_route(doc_id: int, request: Request) -> JSONResponse:
    await _repo(request).delete_document(doc_id)
    return JSONResponse({"id": doc_id, "deleted": True})


# --- instincts -------------------------------------------------------------------------


@app.get("/instincts", tags=["instincts"])
async def list_instincts(request: Request) -> dict:
    return {"instincts": await _repo(request).list_instincts()}


@app.post("/instincts", status_code=202, tags=["instincts"])
async def save_instinct(body: SaveInstinct, request: Request) -> JSONResponse:
    instinct_id = new_instinct_id()
    await _repo(request).save_instinct(instinct_id, body.label, body.spec)
    return _accepted({"instinct_id": instinct_id, "accepted": True})


class InstinctPatch(BaseModel):
    label: str | None = Field(None, min_length=1, max_length=200)
    spec: dict | None = None


@app.get("/instincts/{instinct_id}", tags=["instincts"])
async def get_instinct_route(instinct_id: str, request: Request) -> JSONResponse:
    inst = await _repo(request).get_instinct(instinct_id)
    if inst is None:
        return JSONResponse(status_code=404, content={"detail": "instinct not found"})
    return JSONResponse(content=inst)


@app.patch("/instincts/{instinct_id}", tags=["instincts"])
async def patch_instinct(instinct_id: str, body: InstinctPatch, request: Request) -> JSONResponse:
    """Rename a saved instinct or replace its formation/spec."""
    ok = await _repo(request).update_instinct(instinct_id, body.label, body.spec)
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "instinct not found"})
    return JSONResponse({"instinct_id": instinct_id, "ok": True})


@app.delete("/instincts/{instinct_id}", tags=["instincts"])
async def delete_instinct_route(instinct_id: str, request: Request) -> JSONResponse:
    ok = await _repo(request).delete_instinct(instinct_id)
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "instinct not found"})
    return JSONResponse({"instinct_id": instinct_id, "deleted": True})


@app.post("/parse", tags=["hunts"])
async def parse_document(
    file: UploadFile | None = File(None), url: str | None = Form(None)
) -> JSONResponse:
    """Parse an uploaded file (pdf/csv/md/text) or a URL into plain text the pack can research.
    Inline — no object store. The frontend feeds the returned text into createHunt or /inputs."""
    if url:
        try:
            text = await parse_url(url)
        except Exception as exc:  # noqa: BLE001
            return JSONResponse(status_code=400, content={"detail": f"could not fetch URL: {exc}"})
        return JSONResponse({"kind": "url", "text": text, "chars": len(text)})
    if file is not None:
        data = await _read_capped(file)
        kind = detect_kind(file.filename or "", file.content_type or "")
        if kind == "image":
            text = await describe_image(data, file.content_type or "", file.filename or "")
        elif kind == "video":  # v5.7: pull the audio track and transcribe it
            audio = await extract_audio(data)
            text = ""
            if audio:
                text = (await TRANSCRIBER.transcribe(audio, content_type="audio/mpeg")).text
        else:
            text = parse_bytes(data, kind)
        return JSONResponse({"kind": kind, "text": text, "chars": len(text), "filename": file.filename})
    return JSONResponse(status_code=400, content={"detail": "provide a file or a url"})


@app.post("/transcribe", tags=["hunts"])
async def transcribe(file: UploadFile = File(...)) -> JSONResponse:
    """Transcribe uploaded audio (or a VIDEO's audio track, v5.7) into text for a new hunt. The
    frontend then calls createHunt with the transcript. Offline returns a placeholder."""
    data = await _read_capped(file)
    content_type = file.content_type or ""
    if detect_kind(file.filename or "", content_type) == "video":
        audio = await extract_audio(data)
        if not audio:
            return JSONResponse(
                status_code=400, content={"detail": "couldn't pull audio from that video"}
            )
        data, content_type = audio, "audio/mpeg"
    t = await TRANSCRIBER.transcribe(data, content_type=content_type)
    return JSONResponse({"text": t.text, "provider": t.provider, "duration_s": t.duration_s})


@app.post(
    "/hunts/{hunt_id}/transcribe", status_code=202, response_model=CommandAccepted, tags=["hunts"]
)
async def transcribe_into_hunt(
    hunt_id: str, request: Request, file: UploadFile = File(...)
) -> JSONResponse:
    """Transcribe audio and fold it into a RUNNING hunt: the Supervisor emits transcript_ready +
    input_added and weighs the transcript at the next synthesis step."""
    data = await _read_capped(file)
    t = await TRANSCRIBER.transcribe(data, content_type=file.content_type or "")
    ok = await _registry(request).send(
        hunt_id,
        {
            "type": "add_input",
            "text": t.text,
            "kind": "audio",
            "transcript": True,
            "provider": t.provider,
            "duration_s": t.duration_s,
        },
    )
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "hunt not running here"})
    return _accepted({"hunt_id": hunt_id, "accepted": True})


# NOTE: WS /hunts/:id/stream?from_seq=n is served by the RUST GATEWAY (gateway/), not here.
