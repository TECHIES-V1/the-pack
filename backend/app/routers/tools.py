"""Parse and transcribe routes — file/URL → text utilities."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse

from app.dependencies import _accepted, _read_capped, get_registry
from app.engine.registry import HuntRegistry
from app.schemas import CommandAccepted, ParsedDocResponse, TranscriptResponse
from app.tools.file_parse import detect_kind, parse_bytes, parse_url
from app.tools.transcribe import TRANSCRIBER
from app.tools.video import extract_audio
from app.tools.vision import describe_image

router = APIRouter(tags=["hunts"])


@router.post("/parse", response_model=ParsedDocResponse)
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
        elif kind == "video":
            audio = await extract_audio(data)
            text = ""
            if audio:
                text = (await TRANSCRIBER.transcribe(audio, content_type="audio/mpeg")).text
        else:
            text = parse_bytes(data, kind)
        return JSONResponse(
            {"kind": kind, "text": text, "chars": len(text), "filename": file.filename}
        )
    return JSONResponse(status_code=400, content={"detail": "provide a file or a url"})


@router.post("/transcribe", response_model=TranscriptResponse)
async def transcribe(file: UploadFile = File(...)) -> JSONResponse:
    """Transcribe uploaded audio (or a VIDEO's audio track) into text for a new hunt.
    Offline returns a placeholder."""
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


@router.post(
    "/hunts/{hunt_id}/transcribe",
    status_code=202,
    response_model=CommandAccepted,
)
async def transcribe_into_hunt(
    hunt_id: str,
    file: UploadFile = File(...),
    registry: HuntRegistry = Depends(get_registry),
) -> JSONResponse:
    """Transcribe audio and fold it into a RUNNING hunt: the Supervisor emits transcript_ready +
    input_added and weighs the transcript at the next synthesis step."""
    data = await _read_capped(file)
    t = await TRANSCRIBER.transcribe(data, content_type=file.content_type or "")
    ok = await registry.send(
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
