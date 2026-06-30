"""Hunt lifecycle routes — create, approve, command, artifact, share, and Alpha chat."""
from __future__ import annotations

import asyncio
import base64
import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from openai import APIStatusError, RateLimitError

from app.config import settings
from app.core.intake import (
    _SSE_HEADERS,
    ALPHA_CHAT,
    ALPHA_INTAKE,
    cancel_task,
    last_user,
    looks_like_task,
    parse_intake,
    safe_reply,
    stream_tokens,
)
from app.db.repo import Repo
from app.dependencies import _accepted, get_background, get_client, get_registry, get_repo
from app.engine.benchmark import run_benchmark
from app.engine.core import Emitter
from app.engine.ids import new_hunt_id
from app.engine.refine import refine_brief
from app.engine.registry import HuntRegistry
from app.engine.rehearse import rehearse
from app.engine.supervisor import Supervisor
from app.qwen.client import QwenClient
from app.qwen.types import CallSpec
from app.schemas import (
    AddInput,
    ApprovePlan,
    ArtifactResponse,
    ArtifactsListResponse,
    AskAlpha,
    AskReply,
    CommandAccepted,
    CreateHunt,
    FeedbackBody,
    FeedbackResponse,
    HuntCreated,
    HuntDeleteResponse,
    HuntListResponse,
    HuntPatch,
    HuntPatchResponse,
    HuntSnapshot,
    IntakeBody,
    IntakeReply,
    MessageIn,
    MessagesResponse,
    OkResponse,
    RefineBody,
    RefineResponse,
    RehearseBody,
    RehearseResponse,
    ResolveHold,
    ResumeHunt,
    ScorecardResponse,
    SharedResponse,
    ShareResponse,
    TracksResponse,
)
from app.tools.redact import redact_event

router = APIRouter(tags=["hunts"])

# Allowed download formats — must stay in sync with forge._RENDERERS (guarded by a test).
_DOWNLOADABLE = {"md", "html", "pdf", "docx", "xlsx", "pptx", "png"}


# ---------------------------------------------------------------------------
# Hunt CRUD
# ---------------------------------------------------------------------------


@router.post("/hunts", status_code=202, response_model=HuntCreated)
async def create_hunt(
    body: CreateHunt,
    repo: Repo = Depends(get_repo),
    registry: HuntRegistry = Depends(get_registry),
    client: QwenClient = Depends(get_client),
) -> JSONResponse:
    """Open a hunt. Returns 202 with the new hunt_id; the Supervisor starts planning at once.

    Watch `hunt_created` → `plan_proposed` arrive on the stream, then POST `/plan/approve`.
    """
    hunt_id = new_hunt_id()
    strategy = body.strategy or settings.default_strategy
    raw_input = body.input or ""
    seed_team: list[dict] | None = body.team if body.team else None

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
        client,
        handle.commands,
        source=body.source,
        raw_input=raw_input,
        strategy=strategy,
        seed_team=seed_team,
    )
    handle.task = asyncio.create_task(supervisor.run(), name=f"hunt-{hunt_id}")
    return _accepted({"hunt_id": hunt_id, "state": "planning"})


@router.get("/hunts", response_model=HuntListResponse)
async def list_hunts(
    project_id: str | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Recent hunts, newest first — the Den's Past Hunts list. Optionally scoped to a project.
    Cursor pagination: pass the returned `next_cursor` to page older (null when no more)."""
    hunts = await repo.list_hunts(limit=limit + 1, project_id=project_id, cursor=cursor)
    has_more = len(hunts) > limit
    hunts = hunts[:limit]
    next_cursor = hunts[-1]["created_at"] if (has_more and hunts) else None
    return {"hunts": hunts, "next_cursor": next_cursor}


@router.get("/hunts/{hunt_id}", response_model=HuntSnapshot)
async def get_hunt(hunt_id: str, repo: Repo = Depends(get_repo)) -> JSONResponse:
    """Snapshot: state plus last_seq (for reconnect/replay). 404 if the hunt is unknown."""
    snap = await repo.get_hunt_snapshot(hunt_id)
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


@router.patch("/hunts/{hunt_id}", response_model=HuntPatchResponse)
async def patch_hunt(
    hunt_id: str, body: HuntPatch, repo: Repo = Depends(get_repo)
) -> JSONResponse:
    """Rename or archive a hunt (Den history management)."""
    if body.title is not None:
        await repo.rename_hunt(hunt_id, body.title.strip()[:120])
    if body.archived is not None:
        await repo.set_archived(hunt_id, body.archived)
    if "project_id" in body.model_fields_set:
        await repo.assign_hunt(hunt_id, body.project_id)
    return JSONResponse({"hunt_id": hunt_id, "ok": True})


@router.delete("/hunts/{hunt_id}", response_model=HuntDeleteResponse)
async def delete_hunt(hunt_id: str, repo: Repo = Depends(get_repo)) -> JSONResponse:
    """Delete a hunt and everything hanging off it."""
    await repo.delete_hunt(hunt_id)
    return JSONResponse({"hunt_id": hunt_id, "deleted": True})


# ---------------------------------------------------------------------------
# Hunt commands (202 → stream)
# ---------------------------------------------------------------------------


@router.post("/hunts/{hunt_id}/plan/approve", status_code=202, response_model=CommandAccepted)
async def approve_plan(
    hunt_id: str,
    body: ApprovePlan,
    registry: HuntRegistry = Depends(get_registry),
) -> JSONResponse:
    """Approve the plan and set the Boundary. The hunt begins; events flow on the stream."""
    ok = await registry.send(
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


@router.post("/hunts/{hunt_id}/inputs", status_code=202, response_model=CommandAccepted)
async def add_input(
    hunt_id: str,
    body: AddInput,
    registry: HuntRegistry = Depends(get_registry),
) -> JSONResponse:
    """Mid-hunt input. The pack absorbs it at the next synthesis step without restarting."""
    ok = await registry.send(
        hunt_id, {"type": "add_input", "text": body.text, "kind": body.kind}
    )
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "hunt not running here"})
    return _accepted({"hunt_id": hunt_id, "accepted": True})


@router.post(
    "/hunts/{hunt_id}/holds/{hold_id}/resolve",
    status_code=202,
    response_model=CommandAccepted,
)
async def resolve_hold(
    hunt_id: str,
    hold_id: str,
    body: ResolveHold,
    registry: HuntRegistry = Depends(get_registry),
) -> JSONResponse:
    """Answer an open Hold. The hunt resumes from where it paused."""
    ok = await registry.send(
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


@router.post("/hunts/{hunt_id}/stop", status_code=202, response_model=CommandAccepted)
async def stop_hunt(
    hunt_id: str, registry: HuntRegistry = Depends(get_registry)
) -> JSONResponse:
    """Stop the hunt. Emits `hunt_stopped` and winds the Supervisor down."""
    ok = await registry.send(hunt_id, {"type": "stop"})
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "hunt not running here"})
    return _accepted({"hunt_id": hunt_id, "accepted": True})


@router.post("/hunts/{hunt_id}/resume", status_code=202, response_model=CommandAccepted)
async def resume_hunt(
    hunt_id: str,
    body: ResumeHunt,
    registry: HuntRegistry = Depends(get_registry),
) -> JSONResponse:
    """Resume a Boundary-halted hunt by raising the Boundary."""
    ok = await registry.send(
        hunt_id, {"type": "resume", "boundary_usd": body.boundary_usd}
    )
    if not ok:
        return JSONResponse(status_code=404, content={"detail": "hunt not running here"})
    return _accepted({"hunt_id": hunt_id, "accepted": True})


@router.post("/hunts/{hunt_id}/benchmark", status_code=202, response_model=CommandAccepted)
async def benchmark(
    hunt_id: str,
    repo: Repo = Depends(get_repo),
    client: QwenClient = Depends(get_client),
    background: set = Depends(get_background),
) -> JSONResponse:
    """Run the Lone Wolf vs the Pack. Launches a background scorer."""
    snap = await repo.get_hunt_snapshot(hunt_id)
    if snap is None:
        return JSONResponse(status_code=404, content={"detail": "hunt not found"})
    emitter = Emitter(hunt_id, repo)
    task_desc = snap.get("raw_input", "") or "the task"
    coro = run_benchmark(hunt_id, emitter, repo, client, task_desc)
    task_obj = asyncio.create_task(coro, name=f"benchmark-{hunt_id}")
    background.add(task_obj)
    task_obj.add_done_callback(background.discard)
    return _accepted({"hunt_id": hunt_id, "accepted": True})


# ---------------------------------------------------------------------------
# Hunt reads
# ---------------------------------------------------------------------------


@router.get("/hunts/{hunt_id}/messages", response_model=MessagesResponse)
async def get_messages(hunt_id: str, repo: Repo = Depends(get_repo)) -> dict:
    """The saved Alpha conversation for a hunt (durable, cross-device)."""
    return {"messages": await repo.list_messages(hunt_id)}


@router.post("/hunts/{hunt_id}/messages", status_code=202, response_model=OkResponse)
async def post_message(
    hunt_id: str, body: MessageIn, repo: Repo = Depends(get_repo)
) -> JSONResponse:
    """Append one conversation turn to a hunt's durable chat."""
    await repo.save_message(hunt_id, body.role, body.content)
    return JSONResponse(status_code=202, content={"ok": True})


@router.post("/hunts/{hunt_id}/feedback", response_model=OkResponse)
async def submit_feedback(
    hunt_id: str, body: FeedbackBody, repo: Repo = Depends(get_repo)
) -> JSONResponse:
    """Record a thumbs-up or thumbs-down vote for one Alpha turn."""
    await repo.save_feedback(hunt_id, body.turn_index, body.vote)
    return JSONResponse({"ok": True})


@router.get("/hunts/{hunt_id}/feedback", response_model=FeedbackResponse)
async def get_feedback(hunt_id: str, repo: Repo = Depends(get_repo)) -> dict:
    """The votes recorded on a hunt's Alpha turns + up/down tallies."""
    return await repo.feedback_for_hunt(hunt_id)


@router.get("/hunts/{hunt_id}/scorecard", response_model=ScorecardResponse)
async def get_scorecard(hunt_id: str, repo: Repo = Depends(get_repo)) -> JSONResponse:
    """The latest benchmark Scorecard for a hunt (Lone Wolf vs Pack), or 404 if none yet."""
    events = await repo.replay_events(hunt_id, 0)
    for e in reversed(events):
        if e.type == "benchmark_completed":
            return JSONResponse(content={"hunt_id": hunt_id, "scorecard": e.payload["scorecard"]})
    return JSONResponse(status_code=404, content={"detail": "no benchmark yet"})


@router.get("/hunts/{hunt_id}/tracks/export", response_model=TracksResponse)
async def export_tracks(hunt_id: str, repo: Repo = Depends(get_repo)) -> dict:
    """Redacted Tracks export — the full event log with PII masked in every payload."""
    events = await repo.replay_events(hunt_id, 0)
    redacted = [redact_event(e.model_dump()) for e in events]
    return {"hunt_id": hunt_id, "events": redacted, "redacted": True}


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


@router.get("/hunts/{hunt_id}/artifact", response_model=ArtifactResponse)
async def get_artifact(hunt_id: str, repo: Repo = Depends(get_repo)) -> JSONResponse:
    """The hunt's final artifact (Howler's draft) for the reading view. 404 if none yet."""
    artifact = await repo.get_final_artifact(hunt_id)
    if artifact is None:
        return JSONResponse(status_code=404, content={"detail": "no final artifact yet"})
    return JSONResponse(content=artifact)


@router.post("/hunts/{hunt_id}/refine", status_code=202, response_model=RefineResponse)
async def refine_hunt(
    hunt_id: str,
    body: RefineBody,
    repo: Repo = Depends(get_repo),
    client: QwenClient = Depends(get_client),
) -> JSONResponse:
    """Re-draft + re-forge the brief from its existing claims/sources (no re-scout). The new files
    land on the event stream; the Reward refreshes. 404 if no brief, 400 if it had no sources."""
    art = await repo.get_final_artifact(hunt_id)
    if art is None:
        return JSONResponse(status_code=404, content={"detail": "no brief to refine yet"})
    artifact_id = await refine_brief(repo, client, hunt_id, body.instruction)
    if artifact_id is None:
        return JSONResponse(status_code=400, content={"detail": "no sources to refine"})
    return _accepted({"hunt_id": hunt_id, "artifact_id": artifact_id, "accepted": True})


@router.get("/hunts/{hunt_id}/artifacts", response_model=ArtifactsListResponse)
async def list_artifacts(hunt_id: str, repo: Repo = Depends(get_repo)) -> dict:
    """The forged files for this hunt (the Reward's format tabs) — id + kind only."""
    rows = await repo.list_artifacts(hunt_id)
    return {"artifacts": [r for r in rows if r["kind"] in _DOWNLOADABLE]}


@router.get("/hunts/{hunt_id}/artifacts/{artifact_id}")
async def download_artifact(
    hunt_id: str,
    artifact_id: str,
    request: Request,
    repo: Repo = Depends(get_repo),
) -> Response:
    """Download one forged file — base64-decoded, with the right content-type and a filename.
    Artifacts are immutable so we issue a strong ETag and honor If-None-Match → 304."""
    row = await repo.get_artifact_row(artifact_id)
    if row is None or row["hunt_id"] != hunt_id:
        return JSONResponse(status_code=404, content={"detail": "artifact not found"})
    content = row.get("content") or {}
    b64 = content.get("b64")
    if not b64:
        return JSONResponse(status_code=404, content={"detail": "not a downloadable file"})
    etag = f'"{artifact_id}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    data = base64.b64decode(b64)
    mime = content.get("mime", "application/octet-stream")
    filename = f"pack-brief.{row['kind']}"
    return Response(
        content=data,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "ETag": etag,
            "Cache-Control": "private, max-age=31536000, immutable",
        },
    )


# ---------------------------------------------------------------------------
# Share
# ---------------------------------------------------------------------------


@router.post("/hunts/{hunt_id}/share", response_model=ShareResponse)
async def share_hunt(hunt_id: str, repo: Repo = Depends(get_repo)) -> JSONResponse:
    """Mint (or reuse) a public read-only token for this hunt's brief."""
    token = secrets.token_urlsafe(9)
    await repo.set_share_token(hunt_id, token)
    return JSONResponse({"token": token})


@router.get("/share/{token}", response_model=SharedResponse)
async def get_share(token: str, repo: Repo = Depends(get_repo)) -> JSONResponse:
    """Public read-only view of a shared brief (no hunt id, no chat)."""
    data = await repo.get_shared(token)
    if data is None:
        return JSONResponse(status_code=404, content={"detail": "not found"})
    return JSONResponse(content=data)


# ---------------------------------------------------------------------------
# Rehearse
# ---------------------------------------------------------------------------


@router.post("/hunts/{hunt_id}/rehearse", response_model=RehearseResponse)
async def rehearse_hunt(hunt_id: str, body: RehearseBody) -> dict:
    """Shadow Hunt (safety rail): estimate this team's cost + time before the pack runs."""
    strategy = body.strategy or settings.default_strategy
    team = body.team or [{"role": "scout", "count": 3}]
    return rehearse(team, strategy)


# ---------------------------------------------------------------------------
# Alpha intake (clarify-gate)
# ---------------------------------------------------------------------------


@router.post("/hunts/intake", response_model=IntakeReply)
async def intake(
    body: IntakeBody,
    client: QwenClient = Depends(get_client),
) -> JSONResponse:
    """Front-door clarify-gate: Alpha converses until there's a real task, then signals ready
    with a one-line brief. No hunt is created here — the frontend creates one only on ready=true."""
    msgs = [m for m in body.messages if m.get("content")]
    last = last_user(msgs)

    if client.offline:
        if looks_like_task(last):
            return JSONResponse({
                "reply": "On it — I'll get the Pack on that.",
                "ready": True,
                "brief": last.strip()[:200],
            })
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
                messages=[{"role": "system", "content": ALPHA_INTAKE}, *msgs],
            )
        )
    except RateLimitError as exc:
        raise HTTPException(429, detail="rate_limit") from exc
    except APIStatusError as e:
        if "content_filter" in str(e):
            raise HTTPException(400, detail="content_filter") from e
        raise HTTPException(500, detail=str(e)) from e

    text = (result.text or "").strip()
    parsed = parse_intake(text)
    if parsed is not None:
        _fallback = "Tell me what you want the pack to hunt down."
        reply = str(parsed.get("reply") or "").strip() or _fallback
        ready = bool(parsed.get("ready"))
        brief = str(parsed.get("brief") or "").strip()
    else:
        reply = safe_reply(text)
        ready = False
        brief = ""
    if ready and not brief:
        brief = last.strip()[:200]
    return JSONResponse({"reply": reply, "ready": ready, "brief": brief})


@router.post("/hunts/intake/stream")
async def intake_stream(
    request: Request,
    body: IntakeBody,
    client: QwenClient = Depends(get_client),
) -> StreamingResponse:
    """SSE variant of /intake — yields `token` events as text arrives, then a `done` event."""
    msgs = [m for m in body.messages if m.get("content")]
    last = last_user(msgs)

    if client.offline:
        if looks_like_task(last):
            reply, ready, brief = "On it — I'll get the Pack on that.", True, last.strip()[:200]
        else:
            reply = "I'm Alpha — I lead the Pack. Ask me anything, or tell me what to look into."
            ready, brief = False, ""

        async def _offline_gen():
            yield f"data: {json.dumps({'type': 'token', 'text': reply})}\n\n"
            done = {"type": "done", "reply": reply, "ready": ready, "brief": brief}
            yield f"data: {json.dumps(done)}\n\n"

        return StreamingResponse(
            _offline_gen(), media_type="text/event-stream", headers=_SSE_HEADERS
        )

    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _on_delta(delta: str) -> None:
        await queue.put(delta)

    async def _gen():
        async def _run():
            r = await client.complete(
                CallSpec(
                    hunt_id="intake",
                    wolf_id="alpha",
                    tier="plus",
                    intent="intake",
                    force_stream=True,
                    messages=[{"role": "system", "content": ALPHA_INTAKE}, *msgs],
                ),
                on_delta=_on_delta,
            )
            await queue.put(None)
            return r

        task = asyncio.create_task(_run())
        try:
            async for frame in stream_tokens(queue, request):
                yield frame
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
            parsed = parse_intake(text)
            if parsed is not None:
                reply = str(parsed.get("reply") or "").strip() or "Tell me what you want the pack."
                ready = bool(parsed.get("ready"))
                brief = str(parsed.get("brief") or "").strip()
            else:
                reply, ready, brief = safe_reply(text), False, ""
            if ready and not brief:
                brief = last.strip()[:200]
            done = {"type": "done", "reply": reply, "ready": ready, "brief": brief}
            yield f"data: {json.dumps(done)}\n\n"
        finally:
            await cancel_task(task)

    return StreamingResponse(_gen(), media_type="text/event-stream", headers=_SSE_HEADERS)


# ---------------------------------------------------------------------------
# Alpha ask (side-chat about a hunt)
# ---------------------------------------------------------------------------


@router.post("/hunts/{hunt_id}/ask", response_model=AskReply)
async def ask_alpha(
    hunt_id: str,
    body: AskAlpha,
    repo: Repo = Depends(get_repo),
    client: QwenClient = Depends(get_client),
) -> JSONResponse:
    """A side conversation with Alpha about the hunt — multi-turn, carries the full history."""
    snap = await repo.get_hunt_snapshot(hunt_id)
    task = (snap or {}).get("raw_input", "")
    history = [m for m in body.messages if m.get("content")]
    if not history and body.question:
        history = [{"role": "user", "content": body.question}]
    system = f"{ALPHA_CHAT}\n\nThe hunt you're discussing is about: {task or 'the current task'}."
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


@router.post("/hunts/{hunt_id}/ask/stream")
async def ask_stream(
    hunt_id: str,
    request: Request,
    body: AskAlpha,
    repo: Repo = Depends(get_repo),
    client: QwenClient = Depends(get_client),
) -> StreamingResponse:
    """SSE variant of /ask — yields `token` events then a `done` event with the full reply."""
    snap = await repo.get_hunt_snapshot(hunt_id)
    task_desc = (snap or {}).get("raw_input", "")
    history = [m for m in body.messages if m.get("content")]
    if not history and body.question:
        history = [{"role": "user", "content": body.question}]
    topic = task_desc or "the current task"
    system = f"{ALPHA_CHAT}\n\nThe hunt you're discussing is about: {topic}."
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _on_delta(delta: str) -> None:
        await queue.put(delta)

    async def _gen():
        async def _run():
            r = await client.complete(
                CallSpec(
                    hunt_id=hunt_id,
                    wolf_id="alpha",
                    tier="plus",
                    intent="chat",
                    force_stream=True,
                    messages=[{"role": "system", "content": system}, *history],
                ),
                on_delta=_on_delta,
            )
            await queue.put(None)
            return r

        task = asyncio.create_task(_run())
        try:
            async for frame in stream_tokens(queue, request):
                yield frame
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
            await cancel_task(task)

    return StreamingResponse(_gen(), media_type="text/event-stream", headers=_SSE_HEADERS)
